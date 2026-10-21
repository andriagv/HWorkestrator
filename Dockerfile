FROM python:3.12-slim-bookworm

# g++ (cppwork compile check + screenshots), XeLaTeX (latexwork), fonts with Georgian glyphs
RUN apt-get update && apt-get install -y --no-install-recommends \
        g++ \
        texlive-xetex texlive-latex-recommended texlive-latex-extra texlive-fonts-recommended \
        fonts-freefont-otf fonts-dejavu-core fonts-noto-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY hworkestrator hworkestrator

ENV PYTHONUNBUFFERED=1 WORKDIR=/tmp/hworkestrator
CMD ["python", "-m", "hworkestrator"]
