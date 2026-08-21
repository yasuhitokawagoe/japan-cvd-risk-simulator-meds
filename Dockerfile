FROM python:3.12-slim

WORKDIR /app

ENV OPENBLAS_NUM_THREADS=1 \
    OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    NUMEXPR_NUM_THREADS=1 \
    PYTHONFAULTHANDLER=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD streamlit run app_streamlit_outcomes.py --server.address 0.0.0.0 --server.port $PORT
