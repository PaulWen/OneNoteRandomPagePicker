# Python app to open a random OneNote page

## Overview

This app uses the [Microsoft identity platform endpoint](http://aka.ms/aadv2) to access
the data of Microsoft customers. The [device code
flow](https://docs.microsoft.com/en-us/azure/active-directory/develop/v2-oauth2-device-code)
is used to authenticate a user and then call to a web api, in this case, the [Microsoft
Graph](https://graph.microsoft.io) to retrieve OneNote data.

## Setup

To run this sample, you'll need:

> -   [Python 2.7+](https://www.python.org/downloads/release/python-2713/) or [Python 3+](https://www.python.org/downloads/release/python-364/)
> -   An Azure Active Directory (Azure AD) tenant. For more information on how to get an Azure AD tenant, see [how to get an Azure AD tenant.](https://docs.microsoft.com/azure/active-directory/develop/quickstart-create-new-tenant)

### Step 1: Register the sample with your Azure Active Directory tenant

Some registration is required for Microsoft to act as an authority for your application.

**Choose the Azure AD tenant where you want to create your applications**

1. Sign in to the [Azure portal](https://portal.azure.com).
    > If your account is present in more than one Azure AD tenant, select `Directory + Subscription`, which is an icon of a notebook with a filter next to the alert icon, and switch your portal session to the desired Azure AD tenant.
2. Select **Azure Active Directory** from the left nav.
3. Select **App registrations** from the new nav blade.

**Register the client app**

1. In **App registrations** page, select **New registration**.
1. When the **Register an application page** appears, enter your application's registration information:
    - In the **Name** section, enter a meaningful application name that will be displayed to users of the app, for example `device-code-sample`.
    - In the **Supported account types** section, select the last option **Accounts in any organizational directory and personal Microsoft accounts**.
    - Device Code Flow disables the need for a redirect URI. Leave it blank.
1. Select **Register** to create the application.
1. On the app **Overview** page, find the **Application (client) ID** value and copy it to your _config.json_ file's _client_id_ entry.
1. In **Authentication** select `Add a plattform` and choose `Mobile and desktop applications`. Choose the recommended Redirect URIs for the client. Under _Advanced
   Settings_ activate `Allow public client flows` to support the Device Code Flow.
1. Then `Save` the settings.
1. In the list of pages for the app, select **API permissions**
    - Click the **Add a permission** button and then,
    - Ensure that the **Microsoft APIs** tab is selected
    - In the _Commonly used Microsoft APIs_ section, click on **Microsoft Graph**
    - In the **Delegated permissions** section, ensure that the right permissions are
      checked: **User.Read**, **Notes.Read**, and **Notes.Read.All**. Use the search box
      if necessary.
    - Select the **Add permissions** button

### Step 2: Install dependencies

You'll need to install the dependencies using pip as follows:

```Shell
pip3 install msal requests
```

If the sample fails to run or is outdated, you can try installing the version specific dependencies from requirements.txt.

```Shell
pip3 install -r requirements.txt
```

### Step 3: Configure the app

Ensure that your config.json is correct and saved. A sample config.json can be found
[here](./config.json.example).

### Step 4: Run the app

Start the application, follow the instructions and use a browser to authenticate. The profile for the user you log in with will display in the console.

```Shell
python ./src/main.py config.json
```
