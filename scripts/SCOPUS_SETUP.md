# Scopus API Setup Instructions

The Scopus fetcher requires an API key from Elsevier. Here's how to get one:

## Getting a Scopus API Key

1. **Go to Elsevier Developer Portal**
   - Visit: https://dev.elsevier.com/
   - Click "Get API Key" or "Register"

2. **Create an Account**
   - Sign up with your academic email
   - Complete the registration process

3. **Request API Access**
   - Go to "My API Key" in your dashboard
   - Select "Scopus Search API"
   - Fill out the application form
   - Describe your use case (e.g., "Academic profile automation for personal website")

4. **Get Your API Key**
   - Once approved (usually within 1-2 business days)
   - Copy your API key from the dashboard

## Setting Up the API Key

### Option 1: Environment Variable (Recommended)
```bash
# Windows PowerShell
$env:SCOPUS_API_KEY="your_api_key_here"

# Windows Command Prompt
set SCOPUS_API_KEY=your_api_key_here

# Linux/Mac
export SCOPUS_API_KEY="your_api_key_here"
```

### Option 2: GitHub Actions (for automation)
1. Go to your repository Settings → Secrets and variables → Actions
2. Add a new repository secret named `SCOPUS_API_KEY`
3. Paste your API key as the value

## Testing the Setup

Once you have the API key set up, test it with:

```bash
python fetch_publications.py --sources scopus
```

## API Limits

- **Free tier**: 20,000 requests per year
- **Rate limit**: 9 requests per second
- **Institutional access**: Higher limits may be available

## Troubleshooting

- **401 Unauthorized**: Check that your API key is correct
- **403 Forbidden**: Your key may not have access to the required APIs
- **429 Too Many Requests**: You've hit the rate limit, wait and try again
- **No results**: Check that your Scopus Author ID is correct in config.yml

## Finding Your Scopus Author ID

1. Go to https://www.scopus.com/
2. Search for your name
3. Click on your author profile
4. The Author ID is in the URL: `https://www.scopus.com/authid/detail.uri?authorId=XXXXXXXXXX`
5. Copy the number after `authorId=` to your config.yml as `scopus_author_id`

Your current Author ID in config.yml: `57204622726`