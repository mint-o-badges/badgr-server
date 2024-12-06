## Authentication

Authenticate requests by including an Authorization header of type "Bearer".  For example:

```bash
curl 'https://api.badgr.io/v1/user/profile' -H "Authorization: Bearer YOURACCESSTOKEN"
```

Alternatively you can also pass the token as cookie, to utilize `HttpOnly`  cookies.
To do this, set `withCredentials: true` in your request.
The cookie in your request would then look something like this:
```yaml
Cookie: csrftoken=YOUR_CSRF_TOKEN; access_token=YOUR_ACCESS_TOKEN
```

## Access Tokens

If you want to make requests to our API, you need to obtain an **Access token**.
These are tokens with a limited time of life (24 hours by default). To request tokens, you need to make a POST request to our API.
For security reasons in our application we store the access token in an [HttpOnly](https://owasp.org/www-community/HttpOnly) cookie.
That means that the browser cannot access the content, instead it's passed with the requests as a cookie.
That also means that we don't return the access token in the data section of the response, but in the cookie section.

If you use `cURL` for example this might look like this:
```bash
curl --request POST \
    --url 'https://api.openbadges.education/o/token' \
    --header 'content-type: application/x-www-form-urlencoded' \
    --data 'grant_type=password' \
    --data 'username=YOUR_USERNAME' \
    --data 'password=YOUR_PASSWORD' \
    --data 'client_id=public' --verbose
```

Or with client ID and secret:
```bash
curl --request POST \
    --url 'https://api.openbadges.education/o/token' \
    --header 'content-type: application/x-www-form-urlencoded' \
    --data 'grant_type=client_credentials' \
    --data 'client_id=YOUR_CLIENT_ID' \
    --data 'client_secret=YOUR_CLIENT_SECRET' --verbose
```

The response will then look something like this:
```text
<a lot of verbose messages that aren't relevant>
< Set-Cookie:  access_token=YOUR_ACCESS_TOKEN; expires=Tue, 19 Nov 2024 13:19:00 GMT; HttpOnly; Max-Age=86400; Path=/; Secure
< 
* Connection #0 to host api.openbadges.education left intact
{"expires_in": 86400, "token_type": "Bearer", "scope": "r:profile"}
```
Once again, note that the scope doesn't actually mean anything (yet).
You can read the access token from the `Set-Cookie` value.

## Token Expiration
Access tokens will expire, if an expired token is used a 403 status code will be returned.

The refresh token can be used to automatically renew an access token without requiring the password again.  For example:

```bash
curl -X POST 'https://api.badgr.io/o/token' -d "grant_type=refresh_token&refresh_token=YOURREFRESHTOKEN"
```
