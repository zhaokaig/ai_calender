# AI Calendar

AI Calendar 是一个语音优先的智能日历网页应用。用户可以通过语音或文字描述日程需求，系统会理解指令并在日历中创建、查询、修改或删除日程。

## 演示 Demo 视频

我用夸克网盘给你分享了「智能日历演示.mov」，点击链接或复制整段内容，打开「夸克APP」即可获取。
/~56c43Ypeig~:/
链接：https://pan.quark.cn/s/cee2fb4273a2

## 已实现功能

- 用户注册和登录
- 月视图日历
- 查看每天的日程
- 手动新增、编辑、删除日程
- 支持重复日程和部分重复日程删除
- 短录音、长录音和文字输入
- 语音转文字
- 使用自然语言创建、查询、修改、删除日程
- 前端通过 Docker + Nginx 部署
- 后端通过 Docker + Flask/Gunicorn 部署

## 怎么启动

1. 准备后端环境变量：

```bash
cp backend/.env.example backend/.env
```

然后在 `backend/.env` 中填写自己的 `DASHSCOPE_API_KEY`。

2. 构建并启动：

```bash
docker compose up -d --build
```

3. 打开网页：

```text
http://127.0.0.1:8080
```

4. 停止服务：

```bash
docker compose down
```
