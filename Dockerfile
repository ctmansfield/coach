FROM python:3.11-slim
WORKDIR /app
COPY coach_app/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY coach_app /app/coach_app
ENV PYTHONUNBUFFERED=1
CMD ["python","-m","coach_app.cli.plan_now","--user","00000000-0000-0000-0000-000000000001","--hours","4","--goals","deep_work,hydration,walk"]
