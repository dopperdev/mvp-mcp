# Deploy MCP Security Gateway to Vercel

This guide shows how to deploy the MCP Security Gateway landing page to Vercel for a live demo.

## Prerequisites

- Vercel account (free tier works): https://vercel.com/signup
- Vercel CLI installed (optional but recommended)

## Option 1: Deploy via Vercel CLI (Recommended)

### 1. Install Vercel CLI

```bash
npm install -g vercel
```

### 2. Login to Vercel

```bash
vercel login
```

### 3. Deploy

```bash
# From the project root directory
vercel

# Follow the prompts:
# - Set up and deploy? Yes
# - Which scope? Select your account
# - Link to existing project? No
# - What's your project's name? mcp-security-gateway (or your choice)
# - In which directory is your code located? ./
# - Want to override settings? No

# Your site will be deployed and you'll get a URL like:
# https://mcp-security-gateway-xxx.vercel.app
```

### 4. Deploy to Production

```bash
vercel --prod
```

## Option 2: Deploy via Vercel Dashboard

### 1. Push to GitHub

Make sure all changes are committed and pushed:

```bash
git add .
git commit -m "Add Vercel deployment configuration"
git push origin main
```

### 2. Import to Vercel

1. Go to https://vercel.com/new
2. Click "Import Git Repository"
3. Select your GitHub repository
4. Configure project:
   - **Framework Preset**: Other
   - **Build Command**: (leave empty)
   - **Output Directory**: (leave empty)
   - **Install Command**: `pip install -r api/requirements.txt`
5. Click "Deploy"

### 3. Get Your URL

After deployment completes (usually 1-2 minutes), you'll get a URL like:
```
https://mcp-security-gateway.vercel.app
```

## Option 3: Deploy from This Branch

If you're working on a feature branch:

```bash
# Deploy preview from current branch
vercel

# The URL will be something like:
# https://mcp-security-gateway-git-feature-branch.vercel.app
```

## What Gets Deployed

The Vercel deployment includes:
- ✅ Landing page (fully functional)
- ✅ Health check endpoint (`/health`)
- ✅ API info endpoint (`/api`)
- ❌ Full gateway features (requires database, Redis)

**Note**: This is a DEMO deployment showing only the landing page. For full MCP gateway functionality (authentication, audit logging, security features), you need to self-host using Docker Compose or Kubernetes.

## Vercel Configuration

The deployment uses these files:
- `vercel.json` - Vercel build configuration
- `api/index.py` - Serverless function handler
- `api/requirements.txt` - Python dependencies
- `.vercelignore` - Files to exclude from deployment

## Custom Domain (Optional)

To use a custom domain:

1. Go to your project settings in Vercel dashboard
2. Navigate to "Domains"
3. Add your domain
4. Configure DNS records as instructed

## Environment Variables

For the demo deployment, no environment variables are needed.

For a production deployment with full features, you would need:
- `DATABASE_URL`
- `REDIS_URL`
- `JWT_SECRET`

(These are not applicable to Vercel's serverless deployment - use Docker/K8s for full features)

## Troubleshooting

### Build fails

```bash
# Check build logs in Vercel dashboard or:
vercel logs
```

### Landing page not loading

1. Verify `src/static/landing.html` exists in repository
2. Check that `vercel.json` routes are correct
3. Review function logs in Vercel dashboard

### Function timeout

Vercel has a 10-second timeout for serverless functions (hobby plan).
The landing page should load instantly, so this shouldn't be an issue.

## Monitoring

View deployment logs and analytics:
```bash
# View recent logs
vercel logs

# View specific deployment
vercel logs <deployment-url>
```

Or use the Vercel dashboard: https://vercel.com/dashboard

## Redeployment

Vercel automatically redeploys when you push to your connected Git branch.

Manual redeployment:
```bash
vercel --prod
```

## Clean Up

To remove the deployment:

```bash
# Remove project from Vercel
vercel remove mcp-security-gateway
```

Or delete from the Vercel dashboard.

## Cost

The landing page deployment is **completely free** on Vercel's hobby plan:
- ✅ Free hosting
- ✅ Free SSL certificate
- ✅ Free custom domain support
- ✅ Unlimited bandwidth (fair use)

## Next Steps

After deploying to Vercel:

1. ✅ Share the Vercel URL to showcase the landing page
2. 📊 Monitor traffic in Vercel analytics
3. 🚀 For full MCP gateway features, deploy to:
   - Docker Compose (see README.md)
   - Kubernetes (see DEPLOYMENT.md)
   - AWS ECS (see DEPLOYMENT.md)

---

**Quick Deploy Command:**

```bash
vercel --prod
```

That's it! Your MCP Security Gateway landing page will be live at:
```
https://your-project.vercel.app
```
