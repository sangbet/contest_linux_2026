import os
import cv2
import numpy as np
import time
from rknnlite.api import RKNNLite

# === 关键参数===
MODEL_PATH = '/home/lckfb/project/ball_0724.rknn'
IMG_SIZE = (320, 320)          # 模型输入尺寸
CLASSES = ("Ball",)            # 类别列表
OBJ_THRESH = 0.25
NMS_THRESH = 0.45
# ============================

# ---------- 图像预处理 ----------
def letter_box(im, new_shape, pad_color=(0, 0, 0)):
    """
    保持比例缩放图像，并进行填充
    """
    old_h, old_w = im.shape[:2]
    new_h, new_w = new_shape
    
    # 计算缩放比例
    r = min(new_h / old_h, new_w / old_w)
    resize_h, resize_w = int(old_h * r), int(old_w * r)
    
    # 缩放
    im = cv2.resize(im, (resize_w, resize_h))
    
    # 计算填充
    dh = (new_h - resize_h) // 2
    dw = (new_w - resize_w) // 2
    
    # 填充
    im = cv2.copyMakeBorder(im, dh, new_h - resize_h - dh, 
                                  dw, new_w - resize_w - dw,
                            cv2.BORDER_CONSTANT, value=pad_color)
    return im, r, dw, dh

def get_real_box(boxes, r, dw, dh):
    """
    将模型输出的坐标映射回原图
    """
    real = boxes.copy().astype(np.float32)
    real[:, 0] -= dw; real[:, 2] -= dw
    real[:, 1] -= dh; real[:, 3] -= dh
    real /= r
    return real

# ---------- 后处理（纯 numpy/cv2） ----------
def dfl(position):
    """
    纯 NumPy 实现的 Distribution Focal Loss (DFL) 解码
    输入: (1, 64, H, W) -> 输出: (1, 4, H, W)
    """
    n, c, h, w = position.shape
    p_num = 4
    mc = c // p_num  # 64 // 4 = 16
    
    # Reshape -> (1, 4, 16, H, W)
    y = position.reshape(n, p_num, mc, h, w)
    
    # Softmax (沿着 mc 维度)
    y_exp = np.exp(y - np.max(y, axis=2, keepdims=True))
    y_softmax = y_exp / np.sum(y_exp, axis=2, keepdims=True)
    
    # 计算期望值: sum(prob * index)
    acc = np.arange(mc, dtype=np.float32).reshape(1, 1, mc, 1, 1)
    return np.sum(y_softmax * acc, axis=2)

def box_process(position):
    """
    将 DFL 输出转换为 (x1, y1, x2, y2) 坐标
    """
    gh, gw = position.shape[2:4]
    col, row = np.meshgrid(np.arange(gw), np.arange(gh))
    col = col.reshape(1, 1, gh, gw)
    row = row.reshape(1, 1, gh, gw)
    grid = np.concatenate((col, row), axis=1)
    
    stride = np.array([IMG_SIZE[1] // gh, IMG_SIZE[0] // gw]).reshape(1, 2, 1, 1)

    position = dfl(position)
    
    # 解析中心点偏移
    xy1 = grid + 0.5 - position[:, 0:2]
    xy2 = grid + 0.5 + position[:, 2:4]
    
    # 映射回原图尺度
    return np.concatenate((xy1 * stride, xy2 * stride), axis=1)

def post_process_detect(input_data):
    """
    针对 YOLOv8 检测模型的 9 输出后处理
    """
    boxes, classes_conf, scores = [], [], []
    
    # 你的模型有 9 个输出，分为 3 组
    # 每组结构: [Box(64ch), Class(1ch, 分数), Obj(1ch, 常为冗余)]
    pair_per_branch = 3  
    
    for i in range(3):
        # 索引分配
        # i=0: [0, 1, 2] -> Box, Class, Obj
        # i=1: [3, 4, 5] -> Box, Class, Obj
        # i=2: [6, 7, 8] -> Box, Class, Obj
        
        # 1. 处理 Box
        boxes.append(box_process(input_data[pair_per_branch * i]))
        
        # 2. 处理 Score (单类别情况)
        # input_data[i*3+1] 是类别分数
        # input_data[i*3+2] 是 Objectness (如果你的模型有这个输出)
        # 对于 YOLOv8 单类，通常取 Class 输出即可。
        # 这里为了稳健性，我们构建一个全1矩阵作为 Objectness 的占位，或者相乘
        cls_score = input_data[pair_per_branch * i + 1] # (1, 1, H, W)
        classes_conf.append(cls_score)
        
        # 构造全1分数 (适配标准 Filter 逻辑)
        scores.append(np.ones_like(cls_score))

    def sp_flatten(_in):
        ch = _in.shape[1]
        # (1, C, H, W) -> (1, H, W, C) -> (H*W, C)
        return _in.transpose(0, 2, 3, 1).reshape(-1, ch)

    # 扁平化并合并所有尺度
    boxes = np.concatenate([sp_flatten(v) for v in boxes])
    classes_conf = np.concatenate([sp_flatten(v) for v in classes_conf])
    scores = np.concatenate([sp_flatten(v) for v in scores])

    # 单类别特殊处理：classes_conf 形状为 (N, 1)
    # 置信度 = Class_Score
    scores = classes_conf.reshape(-1)
    
    # ----- 过滤 -----
    mask = scores >= OBJ_THRESH
    boxes = boxes[mask]
    scores = scores[mask]
    
    # 单类别固定为类别 0
    classes = np.zeros(len(scores), dtype=np.int32)
    
    if boxes.shape[0] == 0:
        return None, None, None

    # ----- NMS -----
    x1 = boxes[:, 0]; y1 = boxes[:, 1]; x2 = boxes[:, 2]; y2 = boxes[:, 3]
    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    order = scores.argsort()[::-1]
    
    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(i)
        
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        
        w = np.maximum(0.0, xx2 - xx1 + 1)
        h = np.maximum(0.0, yy2 - yy1 + 1)
        inter = w * h
        
        ovr = inter / (areas[i] + areas[order[1:]] - inter)
        inds = np.where(ovr <= NMS_THRESH)[0]
        order = order[inds + 1]
        
    return boxes[keep], classes[keep], scores[keep]

# ---------- 绘图 ----------
def draw(image, boxes, scores, classes):
    for box, score, cl in zip(boxes, scores, classes):
        # 坐标转整型
        x1, y1, x2, y2 = [int(_b) for _b in box]
        
        # 画框
        cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 2)
        
        # 画标签
        text = f'{CLASSES[cl]} {score:.2f}'
        cv2.putText(image, text, (x1, y1 - 6), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

# ---------- 主流程 ----------
if __name__ == '__main__':
    # 1. 初始化 RKNN
    rknn = RKNNLite()
    
    # 加载模型
    ret = rknn.load_rknn(MODEL_PATH)
    if ret != 0:
        print("加载模型失败！")
        exit(-1)
        
    # 初始化运行环境 (RK3566)
    ret = rknn.init_runtime()
    if ret != 0:
        print("初始化运行时失败！")
        exit(-1)

    # 2. 准备图片
    img_src = cv2.imread('/home/lckfb/project/0.jpg')
    if img_src is None:
        print("读不到图片")
        exit(1)

    old_h, old_w = img_src.shape[:2]
    
    # LetterBox 填充 (黑底)
    img, r, dw, dh = letter_box(img_src.copy(), (IMG_SIZE[1], IMG_SIZE[0]), pad_color=(0,0,0))
    
    # 转换颜色 BGR -> RGB
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # 3. 推理
    # RKNNLite 推理需要 (N, H, W, C) 格式，且通常需要 np.uint8
    # 如果导出时包含了量化/归一化，这里直接用 uint8 即可
    input_data = np.expand_dims(img, axis=0).astype(np.uint8)
    
    start = time.time()
    outputs = rknn.inference(inputs=[input_data])
    end = time.time()
    print(f"推理耗时: {(end-start)*1000:.2f} ms")

    # 4. 后处理
    boxes, classes, scores = post_process_detect(outputs)

    # 5. 结果展示
    if boxes is not None:
        # 坐标还原回原图
        real_boxes = get_real_box(boxes, r, dw, dh)
        
        print(f"检测到 {len(boxes)} 个目标")
        draw(img_src, real_boxes, scores, classes)
        cv2.imwrite('result.jpg', img_src)
        print("结果已保存至 result.jpg")
    else:
        print("未检测到目标")
        cv2.imwrite('result.jpg', img_src)

    rknn.release()
