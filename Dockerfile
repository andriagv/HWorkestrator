FROM python:3.12-slim-bookworm

# g++ (cppwork compile check + screenshots), XeLaTeX (latexwork), fonts with Georgian glyphs
RUN apt-get update && apt-get install -y --no-install-recommends \
        g++ \
        texlive-xetex texlive-latex-recommended texlive-latex-extra texlive-fonts-recommended \
        fonts-freefont-otf fonts-dejavu-core fonts-noto-core \
    && rm -rf /var/lib/apt/lists/*

# non-root user (Hugging Face Spaces runs containers as uid 1000)
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user PATH=/home/user/.local/bin:$PATH PYTHONUNBUFFERED=1 \
    WORKDIR=/tmp/hworkestrator HEALTH_PORT=7860
WORKDIR /home/user/app

COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=user hworkestrator hworkestrator

EXPOSE 7860
CMD ["python", "-m", "hworkestrator"]
