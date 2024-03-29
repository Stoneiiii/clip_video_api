from flask import Flask, request, render_template, request, jsonify, send_file, session, Response
from flask_socketio import SocketIO
import subprocess
import os
import threading
import re
import uuid
from functools import wraps
import config
from flask_sqlalchemy import SQLAlchemy
import datetime

# 开启线程模式，防止socketio收不到信息
async_mode = "threading"

# 初始化flask
app = Flask(import_name=__name__,
            static_url_path='/python',
            static_folder='static',
            template_folder='templates')

# 导入配置文件
app.config.from_object(config)
# 读取全局配置
TMP_DIR = app.config.get('TMP_DIR')  # 缓存目录
FFMPEG_BIN_DIR = app.config.get('FFMPEG_BIN_DIR')  # ffmpeg 脚本目录
# 初始化socketio
socketio = SocketIO(app, async_mode=async_mode)

# 创建数据库组件对象
db = SQLAlchemy(app)
class Clip_video_db(db.Model):
    __tablename__ = 'user_submission'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(255))
    time = db.Column(db.DateTime, nullable=False)

    def __repr__(self):
        return f"<UserSubmission(username='{self.username}', time='{self.time}')>"


def store_submit(username):
    """
    把用户请求存放在本地数据库中
    :param username: 用户名
    :return:
    """
    # 创建 UserSubmission 对象并保存到数据库
    user_submission = Clip_video_db(username=username, time=datetime.datetime.now())
    db.session.add(user_submission)
    db.session.commit()


# 初始化视频处理日志
# {'status': 状态processing/complete/fail, 'progress': 进度百分比, 'id': 视频id, 'user':用户名}
clip_tasks = {}


# 用户认证: 登录认证装饰器
def login_required(func):
    """
    登录认证装饰器
    :param func:
    :return:
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        if session.get("username") != None and session.get("is_login") == True:
            print("已经登录")
            return func(*args, **kwargs)
        else:
            print("没有登录，跳转")
            resp = Response()
            resp.status_code = 200
            resp.data = "<script>window.location.href='/login';</script>"
            return resp

    return wrapper


# 首页
@app.route("/")
@app.route("/index")
@login_required
def index():
    """
    首先路由
    :return: 跳转到首页
    """
    username = session.get("username")
    return render_template("index.html", username=username)


# 用户认证: 登录页
# 用户认证这里只简单获取session，判断用户，生产环境可以使用token来验证，并且封装一个文件夹中
@app.route("/login", methods=["GET", "POST"])
def login():
    """
    登录页面
    :return:
    """
    if request.method == "GET":
        html = """
                <form action="/login" method="post">
                    <p>账号: <input type="text" name="username"></p>
                    <p>密码: <input type="password" name="password"></p>
                    <input type="submit" value="登录">
                </form>
                """
        return html

    if request.method == "POST":
        get_dict = request.form.to_dict()

        get_username = get_dict['username']
        get_password = get_dict['password']

        # 应该从数据库查询并判断，这里直接判断用户名和密码是否合法
        if len(get_username) > 0 and len(get_password) > 0:
            session["username"] = get_username
            session["is_login"] = True
            resp = Response()
            resp.status_code = 200
            resp.data = "<script>window.location.href='/index';</script>"
            return resp
        else:
            return "登陆失败"
    return "未知错误"


# 用户认证:注销
@app.route("/logout", methods=["GET", "POST"])
@login_required
def logout():
    """
    注销当前用户
    :return:
    """
    username = session.get("username")

    # 登出操作
    session.pop("username")
    session.pop("is_login")
    session.clear()
    return "用户 {} 已注销".format(username)


# 剪辑api：功能实现
# 因为功能少，就放一个文件了，后续函数庞大应该放在独立文件夹的独立文件中
@app.route('/api/clip-video', methods=['POST'])
@login_required
def clip_video():
    """
    视频剪辑的 api
    :return: json 视频的id
    """
    try:
        data = request.json
        video_url = data.get('video_url')
        start_time = data.get('start_time')
        end_time = data.get('end_time')

        if not all([video_url, start_time, end_time]):
            raise ValueError("Missing required parameters")

        if not all([is_time_format(start_time), is_time_format(end_time)]):
            raise ValueError("Invalid time format")

        # 判断视频url是否合法
        supported_formats = ['mp4', 'avi', 'flv']  # 可根据需要扩展
        if len(video_url.split(".")) < 2:
            raise ValueError("Video is not supported")
        if video_url.split(".")[-1] not in supported_formats:
            raise ValueError("Video is not supported")
        print(video_url)

        # Generate unique clip ID
        clip_id = str(uuid.uuid4())
        # clip_id = "cb3ffb48-50cd-44eb-8b1f-43443"
        clip_tasks[clip_id] = {'status': 'processing', 'progress': 0, 'id': clip_id, 'user': session.get("username")}

        # 写入请求记录
        store_submit(session.get("username"))

        # Start a new thread to handle the clip task
        thread = threading.Thread(target=process_clip_task, args=(clip_id, video_url, start_time, end_time))
        thread.start()

        return jsonify({'clip_id': clip_id}), 200

    except ValueError as ve:
        return jsonify({'error': str(ve)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 400


# 剪辑api：视频下载api
@app.route('/api/clip-result/<clip_id>/download', methods=['GET'])
@login_required
def download_clip(clip_id):
    """
    视频下载api
    :param clip_id: 视频id
    :return: 视频文件
    """
    clip_filename_path = os.path.join(TMP_DIR, f'clip_{clip_id}.mp4')
    if os.path.exists(clip_filename_path):
        return send_file(clip_filename_path, as_attachment=True)
    else:
        return jsonify({'error': 'file not found'}), 404


# 剪辑api：查询剪辑进度api
@app.route('/api/clip-status/<clip_id>', methods=['GET'])
@login_required
def get_clip_video_status(clip_id):
    """
    查询视频剪辑状态查询的api
    :param clip_id: 视频id
    :return: dic 视频剪辑状态{'status': 状态processing/complete/fail, 'progress': 进度百分比, 'id': 视频id}
    """
    if clip_id in clip_tasks:
        if session.get("username") == clip_tasks[clip_id]["user"]:
            return clip_tasks[clip_id]
        else:
            return jsonify({'error': 'user unauthorized'}), 404
    else:
        return jsonify({'error': 'clip_id not found'}), 404


# 剪辑api：视频剪辑的进程
def process_clip_task(clip_id, video_url, start_time, end_time):
    """
    用command调用ffmpeg进行视频剪辑
    :param clip_id: 视频id
    :param video_url: 视频url
    :param start_time: 视频开始点
    :param end_time: 视频结束点
    :return: None
    """
    # Call FFmpeg to clip the video
    clip_filename = os.path.join(os.getcwd(), TMP_DIR, f'clip_{clip_id}.mp4')
    ffmpeg_path = os.path.join(os.getcwd(), FFMPEG_BIN_DIR)
    ffmpeg_command = (["ffmpeg", '-i', video_url, '-ss', start_time, '-to', end_time, '-c:v', 'copy', '-c:a', 'copy',
                       clip_filename])
    process = subprocess.Popen(ffmpeg_command, shell=True, cwd=ffmpeg_path,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)

    # 实时读取输出信息
    progress = 0
    while True:
        output = process.stdout.readline()
        print(output)
        if not output and process.poll() is not None:
            break
        if output:
            output = output.strip()
            if output.startswith("Duration:"):
                duration = output[10:output.index(",")]
            if output.startswith("size="):
                res = re.search(r'(?<=time=)(?P<time>\S+)', output)
                if res is not None:
                    if res.group() != 'N/A':
                        cur_time = res.group()
                        progress = round(parse_time2sec(cur_time) / parse_time2sec(duration) * 100, 2)
                        clip_tasks[clip_id]['progress'] = progress
                        socketio.emit("response",  # 绑定通信
                                      clip_tasks[clip_id],  # 返回socket数据
                                      namespace="/clip_video_api")
                        if progress > 100:
                            progress = 100
                            clip_tasks[clip_id]['progress'] = progress
                            socketio.emit("response",  # 绑定通信
                                          clip_tasks[clip_id],  # 返回socket数据
                                          namespace="/clip_video_api")
                            break
            # print(output.strip(), flush=True)
    progress = 100
    clip_tasks[clip_id]['progress'] = progress
    socketio.emit("response",  # 绑定通信
                  clip_tasks[clip_id],  # 返回socket数据
                  namespace="/clip_video_api")
    # 检查转码是否成功
    if process.returncode != 0:
        # 转码失败
        print(f"失败")
        clip_tasks[clip_id]['status'] = 'fail'
    else:
        # 转码成功
        print(f"完成")
        clip_tasks[clip_id]['status'] = 'complete'
        # Notify the client that the clip task is completed
        socketio.emit(clip_tasks[clip_id]['user'],
                      {'clip_id': clip_id, 'download_url': f'/api/clip-result/{clip_id}/download'},
                      namespace='/clip_video_api')


# 剪辑api：剪辑视频中使用的时间转换成秒单位
def parse_time2sec(time):
    """
    转换xx:xx:xx.xx为秒
    :param time: 时间字符串
    :return: 对应的多少秒
    """
    h = int(time[0:2])
    m = int(time[3:5])
    s = int(time[6:8])
    ms = int(time[9:12])
    ts = (h * 60 * 60) + (m * 60) + s + (ms / 1000)
    return ts


# 剪辑api：判断时间格式是否合法
def is_time_format(time_str):
    """
    验证时间戳"00:01:30"格式
    :param time_str: 时间字符串
    :return: boolean 是否是时间字符串
    """
    pattern = r'^\d{1,2}:\d{1,2}:\d{1,2}$'
    return bool(re.match(pattern, time_str))


# Websocket
# 当websocket连接成功时,自动触发connect默认方法
@socketio.on("connect", namespace="/clip_video_api")
def connect():
    print("Client connected")


# Websocket
# 当websocket连接失败时,自动触发disconnect默认方法
@socketio.on("disconnect", namespace="/clip_video_api")
def disconnect():
    print("Client disconnected")


if __name__ == '__main__':
    socketio.run(app, debug=True, host="0.0.0.0")
