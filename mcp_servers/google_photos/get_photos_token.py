# from google_auth_oauthlib.flow import InstalledAppFlow

# # Read-only scope for Google Photos albums
# SCOPES = ['https://www.googleapis.com/auth/photoslibrary.readonly']

# # Use your downloaded credentials.json
# flow = InstalledAppFlow.from_client_secrets_file(
#     'credentials.json', SCOPES
# )

# # Start local OAuth flow
# creds = flow.run_local_server(port=0)

# print("\n=== COPY THIS ACCESS TOKEN INTO mcp.json ===")
# print(creds.token)


from google_auth_oauthlib.flow import InstalledAppFlow

flow = InstalledAppFlow.from_client_secrets_file(
    'credentials.json',
    scopes=['https://www.googleapis.com/auth/photoslibrary.readonly']
)
creds = flow.run_local_server(port=0)
print("Refresh token:", creds.refresh_token)