FROM python
RUN pip install pdm
COPY . .
RUN pdm install
CMD pdm run prod
EXPOSE 8000