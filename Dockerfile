FROM python
RUN pip install pdm
COPY . .
RUN pdm install
CMD pdm run dev
EXPOSE 8000