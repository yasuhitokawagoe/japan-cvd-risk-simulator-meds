FROM python:3.12-slim

WORKDIR /app

ENV OPENBLAS_NUM_THREADS=1 \
    OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    NUMEXPR_NUM_THREADS=1 \
    PYTHONFAULTHANDLER=1

# 患者向けPDFへ正しい日本語字形を埋め込む。
ADD https://raw.githubusercontent.com/google/fonts/main/ofl/notosansjp/NotoSansJP%5Bwght%5D.ttf /usr/share/fonts/truetype/noto/NotoSansJP.ttf

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD streamlit run app_streamlit_outcomes.py --server.address 0.0.0.0 --server.port $PORT
