FROM python:3.13.11-trixie

RUN mkdir /opt/deepcas12f
WORKDIR /opt/deepcas12f
COPY ./ ./

RUN printf "%s\n" \
    "deb https://mirrors.tuna.tsinghua.edu.cn/debian/ trixie main contrib non-free non-free-firmware" \
    "deb-src https://mirrors.tuna.tsinghua.edu.cn/debian/ trixie main contrib non-free non-free-firmware" \
    "deb https://mirrors.tuna.tsinghua.edu.cn/debian/ trixie-updates main contrib non-free non-free-firmware" \
    "deb-src https://mirrors.tuna.tsinghua.edu.cn/debian/ trixie-updates main contrib non-free non-free-firmware" \
    "deb https://mirrors.tuna.tsinghua.edu.cn/debian/ trixie-backports main contrib non-free non-free-firmware" \
    "deb-src https://mirrors.tuna.tsinghua.edu.cn/debian/ trixie-backports main contrib non-free non-free-firmware" \
    "deb https://mirrors.tuna.tsinghua.edu.cn/debian-security trixie-security main contrib non-free non-free-firmware" \
    "deb-src https://mirrors.tuna.tsinghua.edu.cn/debian-security trixie-security main contrib non-free non-free-firmware" \
    > /etc/apt/sources.list && \
    apt update && \
    apt install -y ocl-icd-libopencl1 opencl-headers clinfo pocl-opencl-icd && \
    apt clean && \
    rm -rf /var/lib/apt/lists/*


COPY cas-offinder /usr/local/bin

ENV UV_DEFAULT_INDEX=https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple
RUN pip config set global.index-url https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple && \
    pip install uv && uv sync && uv cache clean && \
    chmod +x /usr/local/bin/cas-offinder

# 使用 ENTRYPOINT 固定解释器/运行器
ENTRYPOINT ["uv", "run", "main.py"]

# CMD 提供默认参数（可被 docker run 覆盖）
CMD []
