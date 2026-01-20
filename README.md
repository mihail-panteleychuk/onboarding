<h1>Dropship API</h1>

Export collection json-file for postment import  - /api/api.json
<hr>
<h3>Start Project:</h3>
<ol>
    <li>(Optional but recommended)</li>
        <ol>
            <li>Rename folders from `site_name` to necessary name</li>
            <li>Run search through project with text `site_name`</li>
            <li>Replace all the references with needed project name</li>
        </ol>
    <li>Install docker & docker-compose</li>
        <ul>
            <li>Guide link: https://docs.docker.com/compose/install/</li>
        </ul>
    <li>On servers :</li>
        <ul>
            <li>Edit nginx config `server_name` with correct domain_name or server IP.</li>
            <ul>
                <li>File: <a href="./docker/nginx/nginx.conf">nginx.conf</a>
                <li>Local: [a nginx.conf](./docker/nginx/nginx.conf)
            </ul>
        </ul>
    <li>Build docker containers:</li>
        <ol>
            <li>On Servers:</li>
                <ul>
                    <li>(sudo) docker-compose -f docker-compose.server.yml up --build -d</li>
                </ul>
            <li>Local Start(you do not need nginx container):</li>
                <ul>
                    <li>(sudo) docker-compose -f docker-compose.local.yml up --build -d</li>
                </ul>
        </ol>
    <li>Set up finished</li>

</ol>
<hr>
<h3>Create Django SuperUser:</h3>
<ol>
    <li>Run command:</li>
        <ul>
            <li>(sudo) docker exec -it django python3 manage.py add_admin_user</li>
        </ul>
    <li>Follow the instructions in console</li>
</ol>
<hr>
<h3>Initial Database Start Up</h3>
<ol>
    <li>Run migrations:</li>
        <ol>
            <li>(sudo) docker exec -it django python3 manage.py makemigrations</li>
            <li>(sudo) docker exec -it django python3 manage.py migrate</li>
        </ol>
    <li>run django-command for fill up `Country Table`:</li>
    <ul>
        <li>(sudo) docker exec -it django python3 manage.py add_countries</li>
    </ul>
</ol>


<br><br><hr><hr>
Containers setup: https://pentacent.medium.com/nginx-and-lets-encrypt-with-docker-in-less-than-5-minutes-b4b8a60d3a71
