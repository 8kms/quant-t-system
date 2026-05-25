# VPS deployment

推荐部署方式：Docker Compose。

## 服务器准备

Ubuntu/Debian VPS 上安装 Docker：

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
```

重新登录 SSH 后，进入项目目录：

```bash
docker compose up -d --build
```

访问：

```text
http://你的服务器IP:8000
```

建议先设置访问密码：

```bash
export TQUANT_PASSWORD='换成你的强密码'
export TQUANT_SECRET_KEY='换成一串随机字符'
docker compose up -d --build
```

## 域名和 Nginx

如果你有域名，把 `deploy/nginx/tquant.conf` 里的域名替换掉，然后复制到：

```bash
/etc/nginx/sites-available/tquant.conf
```

再执行：

```bash
sudo ln -s /etc/nginx/sites-available/tquant.conf /etc/nginx/sites-enabled/tquant.conf
sudo nginx -t
sudo systemctl reload nginx
```

## 一键同步脚本

在本机执行：

```bash
bash deploy/sync_to_vps.sh root@你的服务器IP /opt/tquant
```

然后 SSH 到服务器：

```bash
cd /opt/tquant
docker compose up -d --build
```

也可以直接同步并启动：

```bash
bash deploy/deploy_vps.sh root@你的服务器IP /opt/tquant
```

如果要启用密码，先在 VPS 的 `/opt/tquant/.env` 里写入：

```bash
TQUANT_PASSWORD=你的访问密码
TQUANT_SECRET_KEY=一串随机字符
```
