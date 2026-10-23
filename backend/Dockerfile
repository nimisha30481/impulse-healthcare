# Lambda container image for the IMPULSE API, worker and workflow functions.
FROM public.ecr.aws/lambda/python:3.11
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY alembic.ini ./
COPY migrations ./migrations
# The handler is overridden per function in infra/ (api_handler, worker_handler, interaction_workflow_handler)
CMD ["app.lambda_handler.api_handler"]
