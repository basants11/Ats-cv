# AI Fusion Core API Documentation

## Overview

The AI Fusion Core provides a comprehensive dual API architecture with both REST and GraphQL support, along with robust JWT and OAuth2 authentication, role-based access control (RBAC), and advanced security features.

## Architecture

### Dual API Support

The system supports both REST and GraphQL APIs:

- **REST API**: Traditional REST endpoints under `/api/v1/`
- **GraphQL API**: Modern GraphQL interface under `/api/v1/graphql` and `/api/v2/graphql`

### Authentication Architecture

#### JWT Authentication

- **Access Tokens**: Short-lived tokens for API access (default: 8 days)
- **Refresh Tokens**: Long-lived tokens for obtaining new access tokens (default: 30 days)
- **Algorithm**: HS256 (configurable)

#### OAuth2 Integration

- **Google OAuth2**: For Google account authentication
- **GitHub OAuth2**: For GitHub account authentication
- **State Token Validation**: CSRF protection for OAuth2 flows

#### Role-Based Access Control (RBAC)

Four user roles with granular permissions:

1. **Guest**: Limited read-only access
2. **User**: Standard user permissions
3. **Admin**: Administrative permissions
4. **Superuser**: Full system access

### Security Features

- **Rate Limiting**: Configurable request limits per minute
- **Security Headers**: Comprehensive security headers (CSP, HSTS, etc.)
- **CORS Protection**: Configurable cross-origin policies
- **Input Validation**: Pydantic-based request validation
- **Password Hashing**: bcrypt with salt rounds

## API Endpoints

### Authentication Endpoints

#### JWT Authentication

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password123"
}

Response:
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer",
  "expires_in": 691200,
  "user": {
    "id": "user_123",
    "email": "user@example.com",
    "name": "John Doe",
    "role": "user"
  }
}
```

```http
POST /api/v1/auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

```http
POST /api/v1/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password123",
  "name": "John Doe"
}
```

#### OAuth2 Authentication

```http
GET /api/v1/auth/oauth/google/authorize

Response:
{
  "authorization_url": "https://accounts.google.com/o/oauth2/auth?...",
  "state": "random_state_token"
}
```

```http
GET /api/v1/auth/oauth/github/authorize

Response:
{
  "authorization_url": "https://github.com/login/oauth/authorize?...",
  "state": "random_state_token"
}
```

OAuth2 callback URLs:
- Google: `/api/v1/auth/oauth/google/callback`
- GitHub: `/api/v1/auth/oauth/github/callback`

### GraphQL Endpoint

#### Access

```http
POST /api/v1/graphql
Content-Type: application/json
Authorization: Bearer <access_token>

{
  "query": "{ currentUser { id email name role } }"
}
```

```http
GET /api/v1/graphql?query={ currentUser { id email name role } }
Authorization: Bearer <access_token>
```

#### GraphiQL Interface

In development mode, access the interactive GraphQL interface:
- `/api/v1/graphql` (GraphiQL enabled in debug mode)

### Protected Endpoints

All API endpoints (except public ones) require authentication:

```http
GET /api/v1/auth/me
Authorization: Bearer <access_token>
```

## GraphQL Schema

### Types

#### User
```graphql
type User {
  id: ID!
  email: String!
  name: String
  role: String!
  isActive: Boolean!
  createdAt: DateTime!
  updatedAt: DateTime!
}
```

#### CV
```graphql
type CV {
  id: ID!
  title: String!
  userId: String!
  template: String!
  content: String!
  isPublic: Boolean!
  createdAt: DateTime!
  updatedAt: DateTime!
}
```

#### AIAnalysis
```graphql
type AIAnalysis {
  id: ID!
  cvId: String!
  analysisType: String!
  score: Float!
  feedback: String!
  suggestions: [String!]!
  createdAt: DateTime!
}
```

### Queries

```graphql
type Query {
  currentUser: User
  myCvs: [CV!]!
  cv(id: ID!): CV
  myAnalytics: [AnalyticsData!]!
  allUsers: [User!]!  # Admin only
  publicCvs(limit: Int = 10, offset: Int = 0): [CV!]!
}
```

### Mutations

```graphql
type Mutation {
  createCv(input: CVCreateInput!): CV!
  updateCv(id: ID!, input: CVUpdateInput!): CV
  deleteCv(id: ID!): Boolean!
  updateProfile(input: UserUpdateInput!): User
  analyzeCv(input: AIAnalysisInput!): AIAnalysis!
  registerUser(input: UserCreateInput!): User!
}
```

### Example Queries

#### Get Current User
```graphql
{
  currentUser {
    id
    email
    name
    role
    permissions
  }
}
```

#### Create CV
```graphql
mutation {
  createCv(input: {
    title: "Software Engineer CV"
    template: "modern"
    content: "Experienced software engineer..."
  }) {
    id
    title
    template
    createdAt
  }
}
```

#### Analyze CV
```graphql
mutation {
  analyzeCv(input: {
    cvId: "cv_123"
    analysisType: "comprehensive"
  }) {
    score
    feedback
    suggestions
  }
}
```

## Rate Limiting

### Default Limits

- **General API**: 60 requests per minute
- **Authentication**: 5 requests per minute
- **AI Endpoints**: 5 requests per minute
- **Admin Endpoints**: 30 requests per minute

### Rate Limit Headers

```http
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 59
X-RateLimit-Reset: 1609459200
Retry-After: 60
```

## Error Handling

### Authentication Errors

```json
{
  "detail": "Not authenticated",
  "headers": {"WWW-Authenticate": "Bearer"}
}
```

### Permission Errors

```json
{
  "detail": "Permission cv:write required"
}
```

### Rate Limit Errors

```json
{
  "detail": "Rate limit exceeded. Maximum 60 requests per minute.",
  "headers": {
    "Retry-After": "60",
    "X-RateLimit-Limit": "60",
    "X-RateLimit-Remaining": "0"
  }
}
```

## Configuration

### Environment Variables

```bash
# JWT Configuration
JWT_SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=11520
REFRESH_TOKEN_EXPIRE_DAYS=30

# OAuth2 Configuration
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GITHUB_CLIENT_ID=your-github-client-id
GITHUB_CLIENT_SECRET=your-github-client-secret

# Rate Limiting
API_RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS_PER_MINUTE=60

# Security
SECRET_KEY=your-app-secret-key
```

### Settings

Key configuration options in `app/config/settings.py`:

- `API_RATE_LIMIT_ENABLED`: Enable/disable rate limiting
- `GRAPHQL_ENABLED`: Enable/disable GraphQL API
- `SECURITY_HEADERS_ENABLED`: Enable/disable security headers
- `DEFAULT_USER_ROLE`: Default role for new users
- `CORS_ORIGINS`: Allowed CORS origins

## Best Practices

### Authentication

1. **Use HTTPS**: Always use HTTPS in production
2. **Store Tokens Securely**: Use httpOnly cookies or secure storage
3. **Refresh Tokens**: Implement automatic token refresh
4. **Logout**: Properly invalidate tokens on logout

### API Usage

1. **Use GraphQL for Complex Queries**: Leverage GraphQL for efficient data fetching
2. **Respect Rate Limits**: Implement exponential backoff
3. **Handle Errors**: Properly handle authentication and rate limit errors
4. **Use Pagination**: For large datasets, use pagination parameters

### Security

1. **Validate Input**: Always validate user input
2. **Use Roles**: Implement proper role-based access control
3. **Monitor Logs**: Monitor authentication and security logs
4. **Keep Dependencies Updated**: Regularly update security dependencies

## Testing

### Authentication Testing

```bash
# Get access token
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "password"}'

# Use token for authenticated request
curl -X GET "http://localhost:8000/api/v1/auth/me" \
  -H "Authorization: Bearer <access_token>"
```

### GraphQL Testing

```bash
# Query current user
curl -X POST "http://localhost:8000/api/v1/graphql" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -d '{"query": "{ currentUser { id email name } }"}'
```

## Troubleshooting

### Common Issues

1. **Token Expired**: Use refresh token to get new access token
2. **Rate Limited**: Wait for the specified retry-after period
3. **Permission Denied**: Check user role and permissions
4. **CORS Errors**: Ensure proper CORS configuration

### Debug Mode

Enable debug mode for detailed logging and GraphiQL interface:

```python
DEBUG = True
LOG_LEVEL = "DEBUG"
```

## Support

For API support and questions:
- Check the `/docs` endpoint for interactive API documentation
- Review logs for detailed error information
- Monitor `/health` endpoint for system status