# Intuit MCP Server

A Model Context Protocol (MCP) server for Intuit's GraphQL API that allows AI models to interact with QuickBooks data.

## Features

- **OAuth 2.0 Authentication:** Handles authentication with Intuit's API using OAuth 2.0, including automatic access token refresh using a refresh token.
- **Generic GraphQL Execution:** Provides a tool (`intuit_execute_graphql`) to execute arbitrary GraphQL queries and mutations against the Intuit API.
- **Configuration Flexibility:** Uses environment variables and a configuration file (`intuit-mcp-config.json`) for setup.
- **REST Fallback (Internal):** Includes a basic REST API fallback for fetching company information if the GraphQL query fails (this happens internally within the `intuit_execute_graphql` tool).

## Prerequisites

- Python 3.9 or later
- An Intuit Developer account ([https://developer.intuit.com/](https://developer.intuit.com/))
- A QuickBooks Online App with OAuth 2.0 credentials (Client ID, Client Secret) configured for the correct environment (Sandbox or Production).
- A valid Refresh Token for your app.
- Your QuickBooks Company ID (Realm ID) for certain operations.

## Setup

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd intuit-mcp-server
    ```
2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
3.  **Create a `.env` file:** Copy the example file and populate it with your credentials:
    ```bash
    cp .env.example .env
    ```
    Edit `.env` and add your Intuit App's Client ID, Client Secret, Refresh Token, and specify the environment:
    ```dotenv
    # Intuit API Credentials
    INTUIT_CLIENT_ID=your_client_id_here
    INTUIT_CLIENT_SECRET=your_client_secret_here
    INTUIT_REFRESH_TOKEN=your_refresh_token_here

    # Environment (sandbox or production)
    INTUIT_ENVIRONMENT=sandbox
    ```
    
    Additionally, you may want to add your Company ID (Realm ID) which is used in the code for REST API fallback and will be automatically added to GraphQL variables if not present:
    ```dotenv
    INTUIT_COMPANY_ID=your_company_realm_id_here
    ```

4.  **Review MCP Configuration:** The `intuit-mcp-config.json` file defines how an MCP client should run this server:
    ```json
    {
      "mcpServers": {
        "intuit": {
          "command": "python3",
          "args": ["intuit_mcp_server.py"],
          "env": {
            "INTUIT_CLIENT_ID": "${INTUIT_CLIENT_ID}",
            "INTUIT_CLIENT_SECRET": "${INTUIT_CLIENT_SECRET}",
            "INTUIT_REFRESH_TOKEN": "${INTUIT_REFRESH_TOKEN}",
            "INTUIT_ENVIRONMENT": "${INTUIT_ENVIRONMENT:-sandbox}"
          },
          "description": "MCP server for interacting with Intuit's QuickBooks API"
        }
      }
    }
    ```
    
    This configuration uses environment variable interpolation (e.g., `${INTUIT_CLIENT_ID}`). If using with an MCP client, you may need to configure these environment variables in the client environment or modify the configuration to use direct values.

## Obtaining Intuit Credentials

1.  Sign up or log in at [Intuit Developer](https://developer.intuit.com/).
2.  Create a new app, selecting the QuickBooks Online API.
3.  Under the "Keys & OAuth" section for your app (Development or Production), find your **Client ID** and **Client Secret**.
4.  Set up the OAuth 2.0 Redirect URIs for your application.
5.  Use an OAuth 2.0 tool or library (or Intuit's provided tools/playgrounds) to go through the authorization flow for your app and obtain an **Authorization Code**.
6.  Exchange the Authorization Code for an **Access Token** and a **Refresh Token**. Store the **Refresh Token** securely – this is what you need for the `.env` file. The refresh token is long-lived (typically 101 days) and is used by this server to get new access tokens.
7.  Find your **Company ID** (also called Realm ID). You can often find this in the URL when logged into QuickBooks Online, or via API calls after authenticating.

## Usage

### Running the Server Standalone

You can run the server directly using Python. It will listen for MCP messages via standard input/output:

```bash
python3 intuit_mcp_server.py
```

Make sure your `.env` file is in the same directory or the environment variables are set.

### Connecting to an MCP Client

To connect this server to an MCP client system, configure the client to launch the server according to the `intuit-mcp-config.json` file. You'll need to ensure the environment variables are available to the MCP client system, either through its own environment or by modifying the configuration to use direct values.

If you need to include the Company ID (which is used in the code but not in the default configuration), you might want to add it to your configuration:

```json
"env": {
  "INTUIT_CLIENT_ID": "${INTUIT_CLIENT_ID}",
  "INTUIT_CLIENT_SECRET": "${INTUIT_CLIENT_SECRET}",
  "INTUIT_REFRESH_TOKEN": "${INTUIT_REFRESH_TOKEN}",
  "INTUIT_COMPANY_ID": "${INTUIT_COMPANY_ID}",
  "INTUIT_ENVIRONMENT": "${INTUIT_ENVIRONMENT:-sandbox}"
}
```

## Available Tools

This server exposes the following tool to the MCP client:

1.  **`intuit_execute_graphql`**
    *   **Description:** Executes an arbitrary GraphQL query or mutation against the Intuit API. This tool provides maximum flexibility by allowing direct specification of the GraphQL operation and variables. If `INTUIT_COMPANY_ID` is set, it will be automatically added to the variables as `realmId` if not already present.
    *   **Args:**
        *   `query` (str): The complete GraphQL query or mutation string.
        *   `variables` (dict, optional): A dictionary of variables for the query/mutation.
    *   **Returns:** (str) A JSON string containing the full response from the Intuit API, including `data` and/or `errors`.
    *   **Example Usage (within an AI context):**
        ```
        Use the 'intuit_execute_graphql' tool with the following query to get the company name:

        query GetCompanyName {
          company {
            companyName
          }
        }
        ```
    *   **Introspection:** You can use standard GraphQL introspection queries via this tool to explore the available Intuit API schema.

## License

MIT (Assumed - No LICENSE file present)