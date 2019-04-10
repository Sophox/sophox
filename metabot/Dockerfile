FROM python:3
LABEL maintainer='Yuri Astrakhan <YuriAstrakhan@gmail.com>'

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

VOLUME /usr/src/app/_cache

CMD [ "python", "./update_data_items.py" ]
