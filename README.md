<h1>InHome API</h1>


<hr>
<details><summary><b>Start Project:</b></summary>
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
                    <li>File: <a href="./data/nginx/app.conf">app.conf</a>
                    <li>Local: [a app.conf](./data/nginx/app.conf)
                </ul>
            </ul>
        <li>Build docker containers:</li>
            <ol>
                <li>On Servers:</li>
                    <ul>
                        <li>(sudo) docker-compose up --build -d</li>
                    </ul>
                <li>Local Start(you do not need nginx container):</li>
                    <ul>
                        <li>(sudo) docker-compose -f local.docker-compose.yml up --build -d</li>
                    </ul>
            </ol>
        <li>Configuration nginx and ssl certificates in docker</li>
        <a href = "https://pentacent.medium.com/nginx-and-lets-encrypt-with-docker-in-less-than-5-minutes-b4b8a60d3a71">LINK TO DOCS</a>
        <li>Set up finished</li>
    </ol>
</details><hr><hr>


<details><summary><b>Initial Database Start Up</b></summary>
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
<h3>Create Django SuperUser:</h3>
<ol>
    <li>Run command:</li>
        <ul>
            <li>(sudo) docker exec -it django python3 manage.py add_admin_user</li>
        </ul>
    <li>Follow the instructions in console</li>
</ol>
</details><hr><hr>

<details><summary><b>Postman Api documentation</b></summary>
    Project colud be fully imported to as postman API Documentation and Postman Collection
    To import API to Postmen - follow steps below:
    <ol>
        <li>Export collection json-file for postmen import by url - /api/api.json</li>
        <li>Got to postman</li>
        <li>Press Import => File</li>
        <li>Select previously downloaded file</li>
        <li>Follow the insturctions in Postman</li>
    </ol>
</details><hr><hr>



<details><summary><b>APPLICATION DOCUMENTATION</b></summary>
    <ol>
        <details><summary><b>user</b></summary>
            <ul>
                <li>General application with customers data and techichal tables such as: CompanyDetails, Country, ConfrimCode.</li>
            </ul>
        </details>
        <details><summary><b>authentication</b></summary>
            <ul>
                <li>Application with sign-up/in logic, social auth, social-accounts management</li>
                <ul>
                    <li>Logic of creating new customer with email verification</li>
                    <li>Logic of reseting password in case if customer forgot it. Confirmation emails.</li>
                    <li>Handling different situation such as: email already exists, credentials incorrect, etc</li>
                    <li>Connecting/disconecting social accounts from customer profile</li>
                    <li>Generating/Refreshing JWT token pair (Access/Refresh) to grant user access</li>
                    <li>Supported socials: Google, Facebook, Apple</li>
                </ul>
            </ul>
        </details>
        <details><summary><b>admin_panel</b></summary>
            <ul>
                <li>General application for Admin user operations. To get access to views customer must be with <u>ADMIN/MANAGER</u> role.</li>
                <li>Customer managements</li>
                    <ul>
                        <li><i>Retrieve list of customers and their general data</i></li>
                        <li><i>Filtering, ordering and searching customers</i></li>
                        <li><i>Updating customer information</i></li>
                        <li><i>Creating new customers with email confirmation or not</i></li>
                    </ul>
            </ul>
        </details>
        <details><summary><b>config</b></summary>
            <ul>
                <li>Base Django config directory with `settings.py`, `wsgi.py`, etc.</li>
            </ul>
        </details>
        <details><summary><b>core</b></summary>
            <ul>
                <li>Application with some general features such as middlewares, BaseModel, Exception handler, etc.</li>
                <ol>
                    <li>`LangBasedOnUserSettingsMiddleware` - Middleware for detecting language of responses by user selected language.</li>
                    <li>`RequestLogMiddleware` - Middleware for logging all information about requests and their responses.</li>
                    <li>`rest_framework_custom_exception_handler` - function to unify all error responses to structure {'message': {'detail': "<message>"}}</li>
                    <li>`BaseUuidModel` - base parent model for almost all project models. Provide UUID as primary-key, add datetime field of objects create and last_update actions. </li>
                    <li>`utils.py` - provide some general function for sending different emails. Added for DRY.</li>
                </ol>
            </ul>
        </details>
        <details><summary><b>dashboard</b></summary>
            <ul>
                <li>Almost empty application used as basic page for redirect after user sucessfull registration/onboarding steps </li>
                <li>Provide one endpoint which returns up-to-date user info.</li>
            </ul>
        </details>
        <details><summary><b>payments</b></summary>
            <ul>
                <li>Application that contains all the logic to interact with Stripe(Payment Service)</li>
                <li><a href="https://stripe.com/docs/api">Stripe API Docs</a></li>
                <li>All general functions are providen in `utils.py`</li>
                <li>`views.py` - provide:</li>
                    <ol>
                        <li>`CreateCardView` - creating card as payment method for customer and attach it in payment service</li>
                        <li>`CreateSubscriptionView` - create subscription for cusotmer and process paymment. Card could be passed also like to `CreateCardView`</li>
                        <li>`UpdateSubscriptionView` - subscription management operations like : downgrade/upgrade (shceduled), cancel, renew cancel schedule subscription</li>
                        <li>`InvoiceViewSet` - Payment history for user(list of invoices, and thier details)</li>
                        <li>`StripeWebhookView` - Processing webhooks from stripe such as: payment success/failed, subscription update, etc.</li>
                    </ol>
                <li></li>
                <li></li>
            </ul>
        </details>
        <details><summary><b>subscription</b></summary>
            <ul>
                <li>Application that store Subscription and available Plan objects.</li>
                <li>Provide basic endpoint for retrieveing list of plans. Also provide active susbcription or list of subscription history by user</li>
            </ul>
        </details>
    </ol>
</details><hr><hr>

<details><summary><b>POSSIBLE FRAGMENTATION</b></summary>
    <details><summary><b>Disable onboarding and activate user account after email confirmation (password creating) </b></summary>
        <ul>
            <li>You need to change environment variable `ONBOARDING_ENABLED`:</li>
            <ol>
                <li>True - flag 'onboarding finished' is setting to `True` after user create subscription and finish checkout.s</li>
                <li>False - flag 'onboarding finished' is setting to `True` after user sign-up by socail or confirm password.</li>
            </ol>
        </ul>
    </details>
    <details><summary><b>Disable social auth</b></summary>
        <ol>
            <li>Remove: </li>
            <ul>
                <li>all `socail/` urls in application `authentication`</li>
                <li>classes `AppleOAuth2`, `AppleTokenView`, `GoogleTokenView`, `FacebookTokenView` from <u>views.py</u> in application `authentication`</li>
                <li>social fields from user model and their serializers in `user` app</li>
                <li></li>
                <li></li>
            </ul>
        </ol>
    </details>
    <details><summary><b>Diable subscriptions and onboarding</b></summary>
        <ul>
            <li>Remove applications `subscription` and  `payments` from project and INSTALLED_APPS in `settings.py`</li>
            <li>Remove serializing subscription field in `FullUserInfoSerializer`</li>
            <li>Clean environment file and `settings.py` from stripe keys </li>
            <li>Set up environment variable `ONBOARDING_ENABLED` to <i>False</i> </li>
        </ul>
    </details>

<h4>After all segmentations described below - clean `requirements.txt` from unused packages</h4>

</details><hr><hr>
