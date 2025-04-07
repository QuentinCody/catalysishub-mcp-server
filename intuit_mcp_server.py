import os
import httpx
import json
import time
import sys  # Add this import
from urllib.parse import urlencode
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from typing import Any, Dict, Optional

load_dotenv()

# Intuit API Configuration
INTUIT_CLIENT_ID = os.getenv("INTUIT_CLIENT_ID")
INTUIT_CLIENT_SECRET = os.getenv("INTUIT_CLIENT_SECRET")
INTUIT_REFRESH_TOKEN = os.getenv("INTUIT_REFRESH_TOKEN")
INTUIT_ENVIRONMENT = os.getenv("INTUIT_ENVIRONMENT", "sandbox")  # Default to sandbox
INTUIT_COMPANY_ID = os.getenv("INTUIT_COMPANY_ID")

# Debug: Print environment variables
print(f"Debug - Client ID: {INTUIT_CLIENT_ID[:5]}... (length: {len(INTUIT_CLIENT_ID) if INTUIT_CLIENT_ID else 0})", file=sys.stderr)
print(f"Debug - Client Secret: {INTUIT_CLIENT_SECRET[:5]}... (length: {len(INTUIT_CLIENT_SECRET) if INTUIT_CLIENT_SECRET else 0})", file=sys.stderr)
print(f"Debug - Refresh Token: {INTUIT_REFRESH_TOKEN[:5]}... (length: {len(INTUIT_REFRESH_TOKEN) if INTUIT_REFRESH_TOKEN else 0})", file=sys.stderr)
print(f"Debug - Environment: {INTUIT_ENVIRONMENT}", file=sys.stderr)
print(f"Debug - Company ID: {INTUIT_COMPANY_ID}", file=sys.stderr)

if not all([INTUIT_CLIENT_ID, INTUIT_CLIENT_SECRET, INTUIT_REFRESH_TOKEN]):
    print("ERROR: Intuit credentials not found in .env file or environment variables.", file=sys.stderr)

# Intuit GraphQL API endpoints
INTUIT_GRAPHQL_URL = (
    "https://public-e2e.api.intuit.com/2020-04/graphql"
    if INTUIT_ENVIRONMENT == "sandbox"
    else "https://public.api.intuit.com/2020-04/graphql"
)

# Intuit REST API endpoints (as fallback)
INTUIT_REST_API_URL = (
    f"https://sandbox-quickbooks.api.intuit.com/v3/company/{INTUIT_COMPANY_ID}"
    if INTUIT_ENVIRONMENT == "sandbox"
    else f"https://quickbooks.api.intuit.com/v3/company/{INTUIT_COMPANY_ID}"
)

# Intuit OAuth endpoints
INTUIT_OAUTH_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"

# Initialize MCP Server
mcp = FastMCP("intuit", version="0.1.0")
print("Intuit MCP Server initialized.")

# Cache for the access token
token_cache = {
    "access_token": None,
    "expires_at": 0
}

async def get_access_token() -> str:
    """
    Gets a valid OAuth access token for Intuit API.
    Uses refresh token to get a new access token when needed.
    """
    # Check if we have a valid cached token
    current_time = time.time()
    if token_cache["access_token"] and token_cache["expires_at"] > current_time + 60:
        print(f"Debug - Using cached token: {token_cache['access_token'][:10]}...", file=sys.stderr)
        return token_cache["access_token"]
    
    # We need to get a new token
    if not all([INTUIT_CLIENT_ID, INTUIT_CLIENT_SECRET, INTUIT_REFRESH_TOKEN]):
        error_msg = "Missing required Intuit OAuth credentials"
        print(f"Error - {error_msg}", file=sys.stderr)
        raise Exception(error_msg)
    
    print(f"Debug - Getting new access token using refresh token: {INTUIT_REFRESH_TOKEN[:5]}...", file=sys.stderr)
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    data = {
        "grant_type": "refresh_token",
        "refresh_token": INTUIT_REFRESH_TOKEN,
        "client_id": INTUIT_CLIENT_ID,
        "client_secret": INTUIT_CLIENT_SECRET
    }
    
    async with httpx.AsyncClient() as client:
        try:
            print(f"Debug - Making token request to: {INTUIT_OAUTH_URL}", file=sys.stderr)
            print(f"Debug - Request data: grant_type=refresh_token, client_id={INTUIT_CLIENT_ID[:5]}...", file=sys.stderr)
            
            response = await client.post(
                INTUIT_OAUTH_URL,
                headers=headers,
                data=urlencode(data),
                timeout=30.0
            )
            
            print(f"Debug - Token response status: {response.status_code}", file=sys.stderr)
            
            response.raise_for_status()
            
            token_data = response.json()
            token_cache["access_token"] = token_data["access_token"]
            token_cache["expires_at"] = current_time + token_data["expires_in"]
            
            print(f"Debug - Received new access token: {token_cache['access_token'][:10]}...", file=sys.stderr)
            print(f"Debug - Token expires in: {token_data['expires_in']} seconds", file=sys.stderr)
            
            return token_cache["access_token"]
        except Exception as e:
            print(f"Error getting access token: {e}", file=sys.stderr)
            if isinstance(e, httpx.HTTPStatusError):
                print(f"Response content: {e.response.text}", file=sys.stderr)
            raise

async def make_intuit_request(query: str, variables: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Makes an authenticated GraphQL request to the Intuit API.
    Handles OAuth authentication and error checking.
    """
    try:
        # Get access token
        access_token = await get_access_token()
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "User-Agent": "MCPIntuitServer/0.1.0"
        }
        
        # Add company ID to the payload if available
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        if INTUIT_COMPANY_ID and "variables" in payload:
            # Add company ID to variables if not present
            if "realmId" not in payload["variables"]:
                payload["variables"]["realmId"] = INTUIT_COMPANY_ID
        
        print(f"Debug - Making GraphQL request to: {INTUIT_GRAPHQL_URL}", file=sys.stderr)
        print(f"Debug - Query (first 100 chars): {query[:100]}...", file=sys.stderr)
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                INTUIT_GRAPHQL_URL,
                headers=headers,
                json=payload,
                timeout=30.0
            )
            
            print(f"Debug - GraphQL response status: {response.status_code}", file=sys.stderr)
            
            response.raise_for_status()
            result = response.json()
            
            # Check for GraphQL errors within the response body
            if "errors" in result:
                print(f"GraphQL Errors: {result['errors']}", file=sys.stderr)
            
            return result
    except httpx.RequestError as e:
        print(f"HTTP Request Error: {e}", file=sys.stderr)
        return {"errors": [{"message": f"HTTP Request Error connecting to Intuit: {e}"}]}
    except httpx.HTTPStatusError as e:
        print(f"HTTP Status Error: {e.response.status_code} - {e.response.text}", file=sys.stderr)
        error_detail = f"HTTP Status Error: {e.response.status_code}"
        try:
            # Try to parse Intuit's error response if JSON
            err_resp = e.response.json()
            if "errors" in err_resp:
                error_detail += f" - {err_resp['errors'][0]['message']}"
            elif "error" in err_resp and "message" in err_resp["error"]:
                error_detail += f" - {err_resp['error']['message']}"
            else:
                error_detail += f" - Response: {e.response.text[:200]}"
        except json.JSONDecodeError:
            error_detail += f" - Response: {e.response.text[:200]}"
        
        return {"errors": [{"message": error_detail}]}
    except Exception as e:
        print(f"Generic Error during Intuit request: {e}", file=sys.stderr)
        return {"errors": [{"message": f"An unexpected error occurred: {e}"}]}

@mcp.tool()
async def intuit_execute_graphql(query: str, variables: Dict[str, Any] = None) -> str:
    """
    Executes an arbitrary GraphQL query or mutation against the Intuit API.
    This tool provides flexibility for any Intuit GraphQL operation by directly 
    passing queries with full control over selection sets and variables.
    
    ## GraphQL Introspection
    You can discover the Intuit API schema using GraphQL introspection queries such as:
    
    ```graphql
    # Get all available query types
    query IntrospectionQuery {
      __schema {
        queryType { name }
        types {
          name
          kind
          description
          fields {
            name
            description
            args {
              name
              description
              type { name kind }
            }
            type { name kind }
          }
        }
      }
    }
    
    # Get details for a specific type
    query TypeQuery($typeName: String!) {
      __type(name: $typeName) {
        name
        description
        fields {
          name
          description
          type { name kind ofType { name kind } }
        }
      }
    }
    ```
    
    ## Common Intuit Operations
    
    ### Querying QuickBooks Company Information
    ```graphql
    query GetCompanyInfo {
      company {
        companyName
        companyAddr {
          line1
          city
          country
          postalCode
        }
        legalCountry
        fiscalYearStartMonth
      }
    }
    ```
    
    ### Fetching Customers
    ```graphql
    query GetCustomers($first: Int!) {
      customers(first: $first) {
        edges {
          node {
            id
            displayName
            primaryEmailAddr {
              address
            }
            primaryPhone {
              freeFormNumber
            }
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
    }
    ```
    
    ## Pagination
    For paginated results, use the `after` parameter with the `endCursor` from previous queries:
    ```graphql
    query GetNextPage($first: Int!, $after: String) {
      customers(first: $first, after: $after) {
        edges {
          node {
            id
            displayName
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
    }
    ```
    
    ## Error Handling Tips
    - Check for the "errors" array in the response
    - Common error reasons:
      - Invalid GraphQL syntax: verify query structure
      - Unknown fields: check field names through introspection
      - Missing required fields: ensure all required fields are in queries
      - Permission issues: verify API keys have appropriate permissions
    
    ## Variables Usage
    Variables should be provided as a Python dictionary where:
    - Keys match the variable names defined in the query/mutation
    - Values follow the appropriate data types expected by Intuit
    - Nested objects must be structured according to GraphQL input types
    
    Args:
        query: The complete GraphQL query or mutation to execute.
        variables: Optional dictionary of variables for the query. Should match 
                  the parameter names defined in the query with appropriate types.

    Returns:
        JSON string containing the complete response from Intuit, including data and errors if any.
    """
    print(f"Executing intuit_execute_graphql with query: {query[:100]}...", file=sys.stderr)
    
    # Check if the query is already a JSON string containing a "query" field
    # If not, assume it's a raw GraphQL query string
    processed_query = query
    processed_variables = variables or {}
    
    try:
        # Try to parse as JSON
        query_json = json.loads(query)
        if isinstance(query_json, dict) and "query" in query_json:
            processed_query = query_json["query"]
            # If variables were included in the JSON
            if "variables" in query_json and processed_variables is None:
                processed_variables = query_json["variables"]
            print(f"Parsed JSON query object", file=sys.stderr)
        else:
            print(f"JSON object doesn't contain 'query' field", file=sys.stderr)
    except json.JSONDecodeError:
        # Not valid JSON, assume it's a raw GraphQL query
        print(f"Not a JSON object, treating as raw GraphQL", file=sys.stderr)
        processed_query = query

    # Add company ID to variables if available and not already present
    if INTUIT_COMPANY_ID and "realmId" not in processed_variables:
        processed_variables["realmId"] = INTUIT_COMPANY_ID

    # Make the API call
    result = await make_intuit_request(processed_query, processed_variables)
    
    # If GraphQL fails, try REST API for some common queries
    if "errors" in result and INTUIT_COMPANY_ID:
        print("GraphQL query failed, attempting REST API fallback if applicable", file=sys.stderr)
        
        # Only attempt for certain common queries that we can translate to REST
        # This is just a simple example for company info
        if "company" in processed_query.lower() and "companyname" in processed_query.lower():
            try:
                access_token = await get_access_token()
                url = f"{INTUIT_REST_API_URL}/companyinfo/{INTUIT_COMPANY_ID}"
                
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        url,
                        headers={
                            "Authorization": f"Bearer {access_token}",
                            "Accept": "application/json"
                        },
                        timeout=30.0
                    )
                    
                    if response.status_code == 200:
                        rest_result = response.json()
                        result = {
                            "data": {
                                "company": {
                                    "companyName": rest_result.get("CompanyInfo", {}).get("CompanyName"),
                                    "legalName": rest_result.get("CompanyInfo", {}).get("LegalName"),
                                    "companyAddr": rest_result.get("CompanyInfo", {}).get("CompanyAddr"),
                                    "note": "This data was retrieved using REST API fallback"
                                }
                            }
                        }
            except Exception as e:
                print(f"REST API fallback also failed: {e}", file=sys.stderr)

    # Return the raw result as JSON
    return json.dumps(result)

if __name__ == "__main__":
    print("Attempting to run Intuit MCP server via stdio...")
    # Basic check before running
    if not all([INTUIT_CLIENT_ID, INTUIT_CLIENT_SECRET, INTUIT_REFRESH_TOKEN]):
        print("FATAL: Cannot start server, Intuit credentials missing.", file=sys.stderr)
    else:
        print(f"Configured for Intuit Environment: {INTUIT_ENVIRONMENT}", file=sys.stderr)
        try:
            mcp.run(transport='stdio')
            print("Server stopped.", file=sys.stderr)
        except Exception as e:
            print(f"Server error: {e}", file=sys.stderr)