import unittest
from app import app
import json

data = {
  "video_url": "https://vjs.zencdn.net/v/oceans.mp4",
  "start_time": "00:00:05",
  "end_time": "00:00:20"
}

class MyTestCase(unittest.TestCase):

    def setUp(self) -> None:
        app.testing = True
        self.client = app.test_client()

    # 测试没有登录下，访问都跳转，除了login页面
    def test_no_auth(self):
        # 首页
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, b"<script>window.location.href='/login';</script>")
        # 注销页
        resp = self.client.get("/logout")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, b"<script>window.location.href='/login';</script>")
        # 登录页
        resp = self.client.get("/login")
        self.assertEqual(resp.status_code, 200)
        self.assertNotEqual(resp.data, b"<script>window.location.href='/login';</script>")
        # 剪辑api：功能实现
        resp = self.client.post("/api/clip-video", data=data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, b"<script>window.location.href='/login';</script>")
        # 剪辑api：视频下载api
        resp = self.client.get("/api/clip-result/aaaaaa/download")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, b"<script>window.location.href='/login';</script>")
        # 剪辑api：查询剪辑进度api
        resp = self.client.get("/api/clip-status/aaaaaa")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, b"<script>window.location.href='/login';</script>")

    # 测试登录后，正常访问
    def test_auth(self):
        # 登录
        resp = self.client.post("/login", data={"username": "test", "password": "aaa"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, b"<script>window.location.href='/index';</script>")
        # 首页
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertNotEqual(resp.data, b"<script>window.location.href='/login';</script>")
        # 剪辑api：视频下载api
        resp = self.client.get("/api/clip-result/aaaaaa/download")
        self.assertEqual(resp.status_code, 404)
        self.assertNotEqual(resp.data, b"<script>window.location.href='/login';</script>")
        # 剪辑api：查询剪辑进度api
        resp = self.client.get("/api/clip-status/aaaaaa")
        self.assertEqual(resp.status_code, 404)
        self.assertNotEqual(resp.data, b"<script>window.location.href='/login';</script>")

    # 测试剪辑api
    def test_clip_api(self):
        # 登录
        resp = self.client.post("/login", data={"username": "test", "password": "aaa"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, b"<script>window.location.href='/index';</script>")
        # 剪辑api：功能实现
        resp = self.client.post("/api/clip-video", json=data, content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        resp_dict = json.loads(resp.data)
        self.assertIn("clip_id", resp_dict)
        clip_id = resp_dict.get("clip_id")
        # 剪辑api：查询剪辑进度api
        resp = self.client.get("/api/clip-status/{}".format(clip_id))
        self.assertEqual(resp.status_code, 200)
        resp_dict = json.loads(resp.data)
        self.assertIn("status", resp_dict)
        self.assertEqual(resp_dict["user"], "test")



if __name__ == '__main__':
    unittest.main()