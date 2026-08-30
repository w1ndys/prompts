# 曲阜师范大学统一身份认证 — 滑块验证码登录分析

## 1. 系统概况

| 项目 | 说明 |
|------|------|
| 登录系统 | 金智教育 WiseDZ 统一身份认证 |
| 认证方式 | CAS (Central Authentication Service) |
| 认证地址 | `https://ids.qfnu.edu.cn/authserver/login` |
| 目标服务 | `http://libyy.qfnu.edu.cn/api/cas/cas` (图书馆预约系统) |
| 滑块方案 | longbow.slidercaptcha (金智定制) |

## 2. 完整登录流程

```
┌─────────────────────────────────────────────────────────────────┐
│ 步骤1  GET /authserver/login?service=...                        │
│        → 获取 execution, pwdEncryptSalt, JSESSIONID             │
├─────────────────────────────────────────────────────────────────┤
│ 步骤2  GET /authserver/checkNeedCaptcha.htl?username=xxx        │
│        → {"isNeed": true}  (100% 需要滑块)                      │
├─────────────────────────────────────────────────────────────────┤
│ 步骤3  GET /authserver/common/toSliderCaptcha.htl               │
│        → 加载滑块 HTML 片段到页面                                │
├─────────────────────────────────────────────────────────────────┤
│ 步骤4  GET /authserver/common/openSliderCaptcha.htl             │
│        → {"smallImage":"...", "bigImage":"...", "tagWidth":93}  │
│        → 从 smallImage 末尾 16 字节提取 AES 密钥                 │
├─────────────────────────────────────────────────────────────────┤
│ 步骤5  图像匹配 + 轨迹模拟                                        │
│        → OpenCV 模板匹配找到滑块应在位置                          │
│        → 生成模拟人类拖拽的 tracks 数组                           │
├─────────────────────────────────────────────────────────────────┤
│ 步骤6  POST /authserver/common/verifySliderCaptcha.htl          │
│        → sign = encryptPassword(JSON.stringify(payload), key)   │
│        → {"errorCode":1, "errorMsg":"success"}                  │
├─────────────────────────────────────────────────────────────────┤
│ 步骤7  POST /authserver/login?service=...                       │
│        → password = encryptPassword(原始密码, pwdEncryptSalt)    │
│        → 302 → CAS ticket → 自动登录到目标系统                    │
└─────────────────────────────────────────────────────────────────┘
```

## 3. 关键接口详解

### 3.1 检查是否需要验证码

```
GET /authserver/checkNeedCaptcha.htl?username={学号}&_={时间戳}
```

**响应**: `{"isNeed":true}` — 当前所有账号都需要滑块验证码。

### 3.2 获取滑块图片

```
GET /authserver/common/openSliderCaptcha.htl?_={时间戳}
```

**请求头关键字段**:
- `X-Requested-With: XMLHttpRequest` (必须)
- `Referer: https://ids.qfnu.edu.cn/authserver/login?...`

**响应**:
```json
{
    "smallImage": "iVBORw0KGgo...(base64 PNG)",
    "bigImage":   "/9j/4AAQSkZ...(base64 JPG/PNG)",
    "tagWidth": 93,
    "yHeight": 0
}
```

### 3.3 验证滑块

```
POST /authserver/common/verifySliderCaptcha.htl
Content-Type: application/x-www-form-urlencoded

sign={URL编码的AES密文}
```

**响应**:
```json
{"errorCode": 1, "errorMsg": "success"}
```

`errorCode=1` 表示验证通过，其他值表示失败。

### 3.4 登录提交

```
POST /authserver/login?service=http%3A%2F%2Flibyy.qfnu.edu.cn%2Fapi%2Fcas%2Fcas
Content-Type: application/x-www-form-urlencoded

username={学号}&
password={AES加密密码}&
captcha=&
_eventId=submit&
cllt=userNameLogin&
dllt=generalLogin&
lt=&
execution={从步骤1获取}
```

**响应**: `302` 重定向携带 CAS ticket:
```
Location: http://libyy.qfnu.edu.cn/api/cas/cas?ticket=ST-420313-xxx
```

## 4. AES 加密算法实现

### 4.1 源码 (encrypt.js)

```javascript
var $aes_chars = "ABCDEFGHJKMNPQRSTWXYZabcdefhijkmnprstwxyz2345678";
var aes_chars_len = $aes_chars.length;

function randomString(n) {
    var f = "";
    for (i = 0; i < n; i++)
        f += $aes_chars.charAt(Math.floor(Math.random() * aes_chars_len));
    return f;
}

function encryptPassword(n, f) {
    try { return encryptAES(n, f); } catch (c) {}
    return n;
}

function encryptAES(n, f) {
    return f ? getAesString(randomString(64) + n, f, randomString(16)) : n;
}

function getAesString(n, f, c) {
    f = f.replace(/(^\s+)|(\s+$)/g, "");
    f = CryptoJS.enc.Utf8.parse(f);
    c = CryptoJS.enc.Utf8.parse(c);
    return CryptoJS.AES.encrypt(n, f, {
        iv: c,
        mode: CryptoJS.mode.CBC,
        padding: CryptoJS.pad.Pkcs7
    }).toString();
}
```

### 4.2 参数说明

| 参数 | 含义 | 密码加密时的值 | 滑块sign加密时的值 |
|------|------|---------------|-------------------|
| `f` (密钥) | 16字节 UTF-8 字符串 | `HAIAVv0Khp1S6gCs` | smallImage 末尾16字节 |
| `c` (IV) | 16字节随机字符串 | `randomString(16)` | `randomString(16)` |
| 明文前缀 | 64字符随机盐 | `randomString(64)` | `randomString(64)` |
| `n` (原始数据) | 需要加密的内容 | 用户密码 | `JSON.stringify(sliderPayload)` |

### 4.3 加密特征

- **算法**: AES-128-CBC
- **填充**: PKCS7 (块大小 16 字节)
- **密钥推导**: 无，密钥直接作为 16 字节 AES key
- **输出格式**: **标准 base64，无 `Salted__` 前缀** (因为显式传入了 IV，CryptoJS 不会添加 OpenSSL 格式头)
- 明文 = `randomString(64)` + 原始数据，因此密文长度 = `ceil((64 + len(data)) / 16) * 16` 字节

## 5. 滑块密钥提取

滑块 AES 密钥隐藏在 `smallImage` 中：

```python
import base64

small_img_bytes = base64.b64decode(smallImage)
aes_key = small_img_bytes[-16:]  # 最后 16 字节
aes_key_str = aes_key.decode('latin-1')  # 转为字符串，可能含非 ASCII 字符
```

对应的 JavaScript 源码:
```javascript
var d = window.atob(f.smallImage);   // base64 解码
var b = d.length;
for (var c = b - 16; c < b; c++) {
    safeSecure.value += String.fromCharCode(d.charCodeAt(c));
}
```

## 6. 滑块 payload 结构

```json
{
    "canvasLength": 280,
    "moveLength": 150,
    "tracks": [
        {"a": 0,   "b": 0, "c": 0},
        {"a": 5,   "b": 1, "c": 20},
        {"a": 12,  "b": 1, "c": 40},
        {"a": 25,  "b": 2, "c": 60},
        ...
        {"a": 150, "b": 2, "c": 800}
    ]
}
```

| 字段 | 含义 | 说明 |
|------|------|------|
| `a` | x 位移 (px) | 自起始点的累积水平位移 |
| `b` | y 位移 (px) | 自起始点的累积垂直位移 |
| `c` | 时间 (ms) | 自 `mousedown` 起的累积时间 |

### 轨迹采样规则 (来自 longbow.slidercaptcha.js)

1. `mousedown` 时: `tracks = [{a:0, b:0, c:0}]`, 起始时间 `p = Date.now()`
2. `mousemove` 时: 每 20ms 采样一次, 位移 < 2px 则跳过
3. `mouseup` 时: 追加最后一个点 (最终位置)
4. 服务端会校验轨迹合理性 (有 y 轴抖动、时间递增)

## 7. 图像匹配方案

### 7.1 原理

- `smallImage` (Base64 PNG): 拼图块，背景透明
- `bigImage` (Base64 JPG/PNG): 带缺口的背景图
- `tagWidth`: 拼图块宽度 (93px)
- `yHeight`: y 轴偏移 (固定为 0)

### 7.2 OpenCV 方案

```python
import cv2
import numpy as np
import base64

def find_slider_position(small_b64, big_b64):
    # 解码
    small = cv2.imdecode(np.frombuffer(base64.b64decode(small_b64), np.uint8), cv2.IMREAD_UNCHANGED)
    big = cv2.imdecode(np.frombuffer(base64.b64decode(big_b64), np.uint8), cv2.IMREAD_COLOR)

    # small 图去除 alpha 通道，只保留非透明区域
    if small.shape[2] == 4:
        alpha = small[:, :, 3]
        small_rgb = small[:, :, :3]
    else:
        small_rgb = small
        alpha = np.ones(small.shape[:2], dtype=np.uint8) * 255

    # 使用 alpha 通道作为掩码
    small_for_match = cv2.cvtColor(small_rgb, cv2.COLOR_BGR2GRAY)
    big_gray = cv2.cvtColor(big, cv2.COLOR_BGR2GRAY)

    # Canny 边缘检测
    small_edge = cv2.Canny(small_for_match, 50, 150)
    big_edge = cv2.Canny(big_gray, 50, 150)

    # 模板匹配
    result = cv2.matchTemplate(big_edge, small_edge, cv2.TM_CCOEFF_NORMED, mask=alpha)
    _, _, _, max_loc = cv2.minMaxLoc(result)

    return max_loc[0]  # x 坐标
```

### 7.3 备选方案

- **SSIM (结构相似性)**: 逐像素比对，更精确但更慢
- **特征点匹配** (SIFT/ORB): 对缩放/旋转鲁棒，此处不需要
- **ddddocr**: 部分滑块识别库可直接使用

## 8. 其它加密场景

| 场景 | 密钥 | 说明 |
|------|------|------|
| 账号密码登录 | `pwdEncryptSalt` (从 login 页面获取) | 当前值 `HAIAVv0Khp1S6gCs` |
| 滑块 sign | smallImage 末尾 16 字节 | 每次请求随机生成 |
| 动态码登录 | `DEFAULT_SALT` = `rjBFAaHsNkKAhpoi` | 硬编码在 login.js 中 |

## 9. Cookie 管理

整个流程需要维护的 Cookies:

```
route={路由标识}
JSESSIONID={会话ID}
org.springframework.web.servlet.i18n.CookieLocaleResolver.LOCALE=zh_CN
happyVoyage={设备指纹/安全Token}
```

其中 `happyVoyage` 是一个重要的安全 cookie，在整个会话中保持不变。

## 10. 登录成功后的 CAS 回调

```
GET http://libyy.qfnu.edu.cn/api/cas/cas?ticket=ST-420313-xxx
  → 302 到 http://libyy.qfnu.edu.cn/api/cas/cas (设置 PHPSESSID)
  → 前端调用 POST http://libyy.qfnu.edu.cn/api/cas/user
     Body: {"cas":"md5_hash"}
  → 返回 JWT token 和用户信息
```

## 11. 脚本实现要点

1. **Session 管理**: 使用 `requests.Session()` 自动管理 cookies
2. **header 伪装**: 必须携带 `X-Requested-With: XMLHttpRequest` 和 `Referer`
3. **加密实现**: 需要 `pycryptodome` 做 AES-128-CBC，注意与 CryptoJS 的输出格式对齐
4. **滑块位置计算**: OpenCV 模板匹配，`matchTemplate` 后用 `minMaxLoc` 找最佳位置
5. **轨迹生成**: 模拟先快后慢、带微幅 y 抖动的鼠标拖拽轨迹
6. **重试机制**: 滑块失败时有重试逻辑，需处理

## 12. 依赖库

```
requests          HTTP 请求
pycryptodome      AES 加密
opencv-python     图像处理 / 滑块位置检测
numpy             数组运算
```

## 13. 附录: 关键 JS 文件

| 文件 | URL | 作用 |
|------|-----|------|
| encrypt.js | `.../static/common/encrypt.js` | AES 加密 (CryptoJS) |
| login.js | `.../static/web/js/login.js` | 登录逻辑、表单提交 |
| longbow.slidercaptcha.js | `.../sliderCaptcha/js/longbow.slidercaptcha.js` | 滑块核心交互 |
| ids-sliderCaptcha.js | `.../sliderCaptcha/js/ids-sliderCaptcha.js` | 滑块初始化 & 密钥提取 |
