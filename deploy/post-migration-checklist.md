# Post-Migration Checklist

Complete this checklist after migrating from Heroku to AWS.

## Immediate Verification

- [ ] **Health Check**: `curl https://api.example.com/health/`
- [ ] **API Responds**: Test main API endpoints
- [ ] **Admin Panel**: Access https://api.example.com/admin/
- [ ] **SSL Working**: No certificate warnings in browser

## Authentication

- [ ] **Auth0 Login**: Test user login flow
- [ ] **JWT Tokens**: Verify tokens are being issued
- [ ] **Session Persistence**: Check sessions work correctly

## Database

- [ ] **Data Integrity**: Verify key data migrated correctly
- [ ] **Query Performance**: Check response times
- [ ] **Connections**: No connection pool exhaustion

## WebSockets

- [ ] **Connection**: WebSocket connections establish
- [ ] **Messages**: Real-time features work
- [ ] **Reconnection**: Handles disconnects gracefully

## Payments

- [ ] **Stripe Dashboard**: Update webhook URL to AWS endpoint
  - Old: `https://your-heroku-app.herokuapp.com/api/stripe/webhook/`
  - New: `https://api.example.com/api/stripe/webhook/`
- [ ] **Test Webhook**: Send test event from Stripe
- [ ] **Payment Flow**: Complete a test purchase

## External Services

- [ ] **Firebase**: Verify Firebase connections
- [ ] **ChromaDB/Vectors**: Ensure vector operations work
- [ ] **Email/Notifications**: Test any email functionality

## Frontend

- [ ] **Update API URL**: Ensure Netlify env vars point to new API
- [ ] **Test All Features**: Go through main user flows
- [ ] **Check Console**: No CORS or network errors

## Monitoring & Maintenance

- [ ] **CloudWatch**: Set up basic monitoring
  - CPU utilization alarm
  - Memory usage alarm
  - Disk space alarm
- [ ] **Logs**: Verify logging is working
- [ ] **Backups**: RDS automated backups enabled
- [ ] **SSL Renewal**: Certbot timer is active

## DNS & Routing

- [ ] **DNS Propagation**: Verify worldwide using https://dnschecker.org
- [ ] **Old URLs**: Decide on redirect strategy for old Heroku URLs

## Performance

- [ ] **Response Times**: Compare to Heroku baseline
- [ ] **Load Testing**: Basic load test if high traffic expected

## Security

- [ ] **Security Groups**: Only necessary ports open
- [ ] **SSH Access**: Restricted to known IPs
- [ ] **Secrets**: All sensitive data in environment variables
- [ ] **HTTPS Redirect**: HTTP redirects to HTTPS

## Cleanup (After Verification Period)

- [ ] **Heroku App**: Delete or downgrade Heroku app
- [ ] **Heroku Database**: Delete after confirming AWS backup
- [ ] **Old DNS Records**: Remove any Heroku-pointing records
- [ ] **Documentation**: Update team docs with new infrastructure

## Notes

_Add any issues or observations during migration:_

```
Date: 
Notes:


```
