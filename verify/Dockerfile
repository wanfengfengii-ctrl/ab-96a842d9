FROM python:3.13-slim

WORKDIR /srv/verify
COPY acceptance.py ./

# 验收脚本即入口；Compose 中以一次性服务运行：
#   docker compose run --rm verify
ENTRYPOINT ["python", "/srv/verify/acceptance.py"]
