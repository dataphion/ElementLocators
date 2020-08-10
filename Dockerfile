FROM python:3.6-stretch

RUN mkdir srv/api
WORKDIR /srv/api
COPY . .

RUN apt update && apt install tesseract-ocr -y
RUN pip3 install --no-cache-dir uwsgi &&\
    pip3 install --no-cache-dir pytesseract &&\
    pip3 install --no-cache-dir requests &&\
    pip3 install --no-cache-dir opencv-python==3.4.2.16

RUN apt-get update -y && apt-get install pkg-config -y && apt-get install git -y && apt-get install check -y \
    && apt-get install libglib2.0-dev -y && apt-get install libreadline-dev -y && apt-get install libudev-dev -y && apt-get install libsystemd-dev -y \
    && apt-get install libusb-dev -y && apt-get install cmake -y && apt-get install -y build-essential -y && apt-get install libsystemd-dev -y \
    && apt-get install gobject-introspection -y && apt-get install libgirepository1.0-dev -y && apt-get install libcairo2-dev -y && apt-get install libglib2.0-dev -y \
    && apt-get install python-cairocffi -y && apt-get install python3-cairocffi -y && apt-get install python3-cairo-dev -y

RUN pip3 install --no-cache-dir -r requirements.txt

RUN apt-get update \
    && apt-get install -y \
    build-essential \
    cmake \
    git \
    wget \
    unzip \
    yasm \
    pkg-config \
    libswscale-dev \
    libtbb2 \
    libtbb-dev \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libavformat-dev \
    libpq-dev \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /
ENV OPENCV_VERSION="4.1.0"
RUN wget https://github.com/opencv/opencv/archive/${OPENCV_VERSION}.zip \
    && unzip ${OPENCV_VERSION}.zip \
    && mkdir /opencv-${OPENCV_VERSION}/cmake_binary \
    && cd /opencv-${OPENCV_VERSION}/cmake_binary \
    && cmake -DBUILD_TIFF=ON \
    -DBUILD_opencv_java=OFF \
    -DWITH_CUDA=OFF \
    -DWITH_OPENGL=ON \
    -DWITH_OPENCL=ON \
    -DWITH_IPP=ON \
    -DWITH_TBB=ON \
    -DWITH_EIGEN=ON \
    -DWITH_V4L=ON \
    -DBUILD_TESTS=OFF \
    -DBUILD_PERF_TESTS=OFF \
    -DCMAKE_BUILD_TYPE=RELEASE \
    -DCMAKE_INSTALL_PREFIX=$(python3.6 -c "import sys; print(sys.prefix)") \
    -DPYTHON_EXECUTABLE=$(which python3.6) \
    -DPYTHON_INCLUDE_DIR=$(python3.6 -c "from distutils.sysconfig import get_python_inc; print(get_python_inc())") \
    -DPYTHON_PACKAGES_PATH=$(python3.6 -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())") \
    .. \
    && make install \
    && rm /${OPENCV_VERSION}.zip \
    && rm -r /opencv-${OPENCV_VERSION}

RUN ln -s \
    /usr/local/python/cv2/python-3.6/cv2.cpython-37m-x86_64-linux-gnu.so \
    /usr/local/lib/python3.6/site-packages/cv2.so


RUN pip3 install supervisor
RUN mkdir -p /var/log/supervisor
RUN mkdir -p /opt/images

COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

WORKDIR /opt/services/
COPY . .

EXPOSE 9502
CMD ["/usr/bin/supervisord" ]