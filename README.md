# clip_video_api
# 介绍

为某在线视频剪辑产品编写⼀个 (或⼀组)接⼝，⽤户提交⼀个视频的URL 和想要剪辑的起始、终 ⽌时间戳；后端调⽤ffmpeg 对视频进⾏剪辑；剪辑完成后，⽤ 户可以获取下载剪辑后视频的URL。

# 环境

- 修改Mysql 数据库连接信息
- 创建 一个表：user_submission

```sql
CREATE TABLE user_submission (
    username VARCHAR(255) NOT NULL,
    time DATETIME NOT NULL
);
```

- 取余环境在requirement.txt中

# API 说明

## /

首页

- 有用户验证，没有登录则跳转登录页
- 用户发起视频剪辑api，剪辑完成后会在对应用户首页弹出提示，显示下载连接。

## /login

登录页

传入form表单

1.  username
2.  password

- 这里用户合法性只判断了用户名和密码长度是否合法，后续生产环境需要从数据库中读取验证，转为token
- 返回用户的session

## /logout

注销页

- 用户注销
- 未登录用户，跳转登录页

## /api/clip-video

视频剪辑api

传入：json

1.  video_url: 视频url
2.  start_time: 剪辑开始点  格式要求:00:00:00
3.  end_time: 剪辑结束点   格式要求:00:00:00

返回：json

1.  clip_id: 视频id  格式：uuid 

- 可创建多个剪辑视频的线程
- 对传入参数进行了简单的拦截。剪辑时间是否在视频时间范围内，这个应该是另外一个API实现，以后完成
- 视频剪辑完成后，会给用户发送一个完成事件，会在首页弹窗显示下载连接
- 用户提交请求会保存在本地数据库中持久化

## /api/clip-result/&lt;clip_id&gt;/download

视频下载api

传入：json

1.  clip_id: 视频id 格式： uuid

返回：

1.  文件存在：视频下载文件
2.  不存在json: {'error': 'clip_id not found'}

- 只有提交请求的用户才能下载该视频，否则会返回404 和json{'error': 'user unauthorized'}

## /api/clip-status/&lt;clip_id&gt;

视频剪辑进度查询api

传入：json

1.  clip_id: 视频id 格式： uuid

返回：json

1.  status：processing剪辑中，fail：失败，complete：完成
2.  progress：进度百分比
3.  id：视频的唯一id
4.  user：请求用户名

- 只有提交请求的用户才能查询视频进度，否则会返回404 和json

# 部署

修改conflg.py文件中信息