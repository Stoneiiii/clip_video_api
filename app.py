import uuid

from flask import Flask, request, render_template, request, jsonify, send_file
from flask_socketio import SocketIO
import subprocess
import os
import threading
import re

FFMPEG_BIN_DIR = r'ffmpeg-6.1.1\bin'
TMP_DIR = r'tmp'

async_mode = "threading"

app = Flask(import_name=__name__,
            static_url_path='/python',  # 配置静态文件的访问url前缀
            static_folder='static',  # 配置静态文件的文件夹
            template_folder='templates')  # 配置模板文件的文件夹

app.config['SECRET_KEY'] = "leihu"
socketio = SocketIO(app, async_mode=async_mode)

clip_tasks = {}

@app.route("/")
def index():
    return render_template("index.html")


@app.route('/api/clip-video', methods=['POST'])
def clip_video():
    data = request.json
    video_url = data.get('video_url')
    start_time = data.get('start_time')
    end_time = data.get('end_time')

    print(video_url)
    # Generate unique clip ID
    clip_id = str(uuid.uuid4())
    # clip_id = "cb3ffb48-50cd-44eb-8b1f-43443"
    clip_tasks[clip_id] = {'status': 'processing', 'progress': 0, 'id': clip_id}

    # Start a new thread to handle the clip task
    thread = threading.Thread(target=process_clip_task, args=(clip_id, video_url, start_time, end_time))
    thread.start()

    return jsonify({'clip_id': clip_id}), 200


@app.route('/api/clip-result/<clip_id>/download', methods=['GET'])
def download_clip(clip_id):
    clip_filename_path = os.path.join(TMP_DIR, f'clip_{clip_id}.mp4')
    if os.path.exists(clip_filename_path):
        return send_file(clip_filename_path, as_attachment=True)
    else:
        return jsonify({'error': 'file not found'}), 404


@app.route('/api/clip-result/<clip_id>', methods=['GET'])
def get_clip_video_status(clip_id):
    return clip_tasks[clip_id]

def process_clip_task(clip_id, video_url, start_time, end_time):
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
                        clip_tasks[clip_id] = {'status': 'processing', 'progress': progress, 'id': clip_id}
                        socketio.emit("response",  # 绑定通信
                                      clip_tasks[clip_id],  # 返回socket数据
                                      namespace="/clip_video_api")
                        if progress > 100:
                            progress = 100
                            clip_tasks[clip_id] = {'status': 'processing', 'progress': progress, 'id': clip_id}
                            socketio.emit("response",  # 绑定通信
                                          clip_tasks[clip_id],  # 返回socket数据
                                          namespace="/clip_video_api")
                            break
            # print(output.strip(), flush=True)
    progress = 100
    clip_tasks[clip_id] = {'status': 'processing', 'progress': progress, 'id': clip_id}
    socketio.emit("response",  # 绑定通信
                  clip_tasks[clip_id],  # 返回socket数据
                  namespace="/clip_video_api")
    # 检查转码是否成功
    if process.returncode != 0:
        # 转码失败
        print(f"失败")
    else:
        # 转码成功
        print(f"完成")
        clip_tasks[clip_id] = {'status': 'complete', 'progress': progress, 'id': clip_id}
        # Notify the client that the clip task is completed
        socketio.emit('complete_msg',
                      {'clip_id': clip_id, 'download_url': f'/api/clip-result/{clip_id}/download'},
                      namespace='/clip_video_api')

def parse_time2sec(time):
    h = int(time[0:2])
    m = int(time[3:5])
    s = int(time[6:8])
    ms = int(time[9:12])
    ts = (h * 60 * 60) + (m * 60) + s + (ms / 1000)
    return ts




# 当websocket连接成功时,自动触发connect默认方法
@socketio.on("connect", namespace="/clip_video_api")
def connect():
    print("Client connected")


# 当websocket连接失败时,自动触发disconnect默认方法
@socketio.on("disconnect", namespace="/clip_video_api")
def disconnect():
    print("Client disconnected")




if __name__ == '__main__':
    socketio.run(app, debug=True, host="0.0.0.0")
