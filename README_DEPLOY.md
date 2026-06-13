# Remake_X Deployment Guide

This guide details the deployment process for the Remake_X application using Docker Compose or Kubernetes (K3s).

## Local Development Setup

To run the application locally with hot-reloading:

1. Setup environment variables:
   `cp .env.example .env`
2. Run the application:
   `make dev`
3. Apply database migrations:
   `make migrate`

## Production Docker Deploy

For a standard VPS deployment using Docker Compose:

1. Setup production environment:
   `cp .env.example .env` (and edit it with real secrets)
2. Bring up the stack in detached mode:
   `make prod`
3. Apply database migrations:
   `make migrate`
4. Collect static files:
   `docker-compose exec web python manage.py collectstatic --no-input`
5. Optional - Check the logs:
   `make logs`

## K3s Kubernetes Deployment

Ensure your `kubectl` is configured to point to your K3s cluster.

1. Create the namespace:
   `kubectl apply -f k8s/namespace.yaml`
2. Create secrets from your `.env` file:
   `kubectl create secret generic remake-secret --from-env-file=.env.prod -n remake-x`
3. Apply configurations and deployments:
   `kubectl apply -f k8s/configmap.yaml`
   `kubectl apply -f k8s/deployment-web.yaml`
   `kubectl apply -f k8s/deployment-worker.yaml`
   `kubectl apply -f k8s/deployment-beat.yaml`
4. Expose the services and ingress:
   `kubectl apply -f k8s/service.yaml`
   `kubectl apply -f k8s/ingress.yaml`
5. Enable autoscaling:
   `kubectl apply -f k8s/hpa.yaml`

## Odoo Sync Operations

### Trigger a Manual Sync
To start a full synchronization manually:
`make sync-now`
*(Alternatively, you can trigger this from the Django Admin Dashboard).*

### Check Sync Health
To check if the Odoo connection is healthy:
`curl -f http://localhost/api/v1/odoo-sync/health/`

## Rollback Procedure

If a deployment fails, you can roll back to the previous deployment.

**Docker Compose:**
1. Re-pull the previous working image explicitly: `docker pull ghcr.io/<repo>/remake_x:<previous_tag>`
2. Update the `.env` or `docker-compose.yml` to use that tag.
3. Run `make prod` again.

**Kubernetes:**
`kubectl rollout undo deployment/remake-web -n remake-x`
`kubectl rollout undo deployment/remake-worker -n remake-x`
`kubectl rollout undo deployment/remake-beat -n remake-x`
