# Safaricom Auth Api
This is a lightweight authentication and organisation management API built with Flask and PostgreSQL. It supports user registration, login, JWT-based authentication, and basic organisation CRUD operations.
## CREATING A USER
###  Create a User model using the properties below
_NB: user id and email must be unique_
```json
{
	"userId": "string" // must be unique
	"firstName": "string", // must not be null
	"lastName": "string" // must not be null
	"email": "string" // must be unique and must not be null
	"password": "string" // must not be null
	"phone": "string"
}
```
Provide validation for all fields. When there’s a validation error, return status code **`422`** with payload:
```json
{
  "errors": [
    {
      "field": "string",
      "message": "string"
    },
  ]
}
```
_Using the schema above, implement user authentication_
#### User Registration:  
- Implement an endpoint for user registration  
- Hash the user’s password before storing them in the database.  
- successful response: Return the payload with a **`201`** success status code.
#### User Login
- Implement an endpoint for user Login.
- Use the **`JWT`** token returned to access PROTECTED endpoints.


## CREATING ORGANISATIONS
### Organisation
- A user can belong to one or more organisations
- An organisation can contain one or more users.
- On every registration, an organisation must be created.
- The name property of the organisation takes the user’s firstName and appends “Organisation” to it. For example: user’s first name is John , organisation name becomes "John's Organisation" because firstName = "John" .
- Logged in users can access organisations they belong to and organisations they created.

### Create an organisation model with the properties below.
#### Organisation Model:
```json
{
	"orgId": "string", // Unique
	"name": "string", // Required and cannot be null
	"description": "string",
}
```
## Endpoints

_[POST] /auth/register Registers a users and creates a default organisation Register_  
### request body:
```json
{
	"firstName": "string",
	"lastName": "string",
	"email": "string",
	"password": "string",
	"phone": "string",
}
```
#### Successful response: Return the payload below with a **`201`** success status code.
```json
{
    "status": "success",
    "message": "Registration successful",
    "data": {
      "accessToken": "eyJh...",
      "user": {
	      "userId": "string",
	      "firstName": "string",
				"lastName": "string",
				"email": "string",
				"phone": "string",
      }
    }
}
```
#### Unsuccessful registration response:
```json
{
    "status": "Bad request",
    "message": "Registration unsuccessful",
    "statusCode": 400
}
```
---

_[POST] /auth/login : logs in a user. When you log in, you can select an organisation to interact with_
### Login request body:
```json
{
	"email": "string",
	"password": "string",
}
```
#### Successful response: Return the payload below with a **`200`** success status code.
```json
{
    "status": "success",
    "message": "Login successful",
    "data": {
      "accessToken": "eyJh...",
      "user": {
	      "userId": "string",
	      "firstName": "string",
				"lastName": "string",
				"email": "string",
				"phone": "string",
      }
    }
}
```
#### Unsuccessful login response:
```json
{
    "status": "Bad request",
    "message": "Authentication failed",
    "statusCode": 401
}
```
---
_[GET] /api/users/:id : a user gets their own record or user record in organisations they belong to or created [PROTECTED]._
#### Successful response: Return the payload below with a **`200`** success status code.
```json
{
    "status": "success",
    "message": "<message>",
    "data": {
      "userId": "string",
      "firstName": "string",
			"lastName": "string",
			"email": "string",
			"phone": "string"
    }
}
```
---
_[GET] /api/organisations : gets all your organisations the user belongs to or created. If a user is logged in properly, they can get all their organisations. They should not get another user’s organisation [PROTECTED]._
#### Successful response: Return the payload below with a **`200`** success status code.
```json
{
    "status": "success",
		"message": "<message>",
    "data": {
      "organisations": [
	      {
		      "orgId": "string",
					"name": "string",
					"description": "string",
	      }
      ]
    }
}
```
---
_[GET] /api/organisations/:orgId the logged in user gets a single organisation record [PROTECTED]_
#### Successful response: Return the payload below with a **`200`** success status code.
```json
{
    "status": "success",
		"message": "<message>",
    "data": {
			"orgId": "string", // Unique
			"name": "string", // Required and cannot be null
			"description": "string",
	}
}
```
---
_[POST] /api/organisations : a user can create their new organisation [PROTECTED]._

### Request body: request body must be validated
```json
{
	"name": "string", // Required and cannot be null
	"description": "string",
}
```
#### Successful response: Return the payload below with a **`201`** success status code.
```json
{
    "status": "success",
    "message": "Organisation created successfully",
    "data": {
	      "orgId": "string", 
				"name": "string", 
				"description": "string"
    }
}
```
#### Unsuccessful response:
```json
{
    "status": "Bad Request",
    "message": "Client error",
    "statusCode": 400
}
```
---
_[POST] /api/organisations/:orgId/users : adds a user to a particular organisation_
#### Request body:
```json
{
	"userId": "string"
}
```
#### Successful response: Return the payload below with a **`200`** success status code.
```json
{ 
    "status": "success",
    "message": "User added to organisation successfully",
}
```
---
## UNIT TESTING
- Write appropriate unit tests to cover
- Token generation - Ensure the token expires at the correct time and correct user details are found in the token.
- Organisation - Ensure users can’t see data from organisations they don’t have access to.
### End-to-End Test Requirements for the Register Endpoint
- The goal is to ensure the POST /auth/register endpoint works correctly by performing end-to-end tests. The tests should cover successful user registration, validation errors, and database constraints.
### Directory Structure:
- The test file should be named auth.spec.ext (ext is the file extension of your chosen language) inside a folder named tests . For example tests/auth.spec.ts assuming I’m using Typescript
#### Test Scenarios:
- It Should Register User Successfully with Default Organisation:Ensure a user is registered successfully when no organisation details are provided.
- Verify the default organisation name is correctly generated (e.g., "John's Organisation" for a user with the first name "John").
- Check that the response contains the expected user details and access token.
- It Should Log the user in successfully:Ensure a user is logged in successfully when a valid credential is provided and fails otherwise.
- Check that the response contains the expected user details and access token.
- It Should Fail If Required Fields Are Missing:Test cases for each required field (firstName, lastName, email, password) missing.
- Verify the response contains a status code of 422 and appropriate error messages.
It Should Fail if there’s Duplicate Email or UserID:Attempt to register two users with the same email.
- Verify the response contains a status code of 422 and appropriate error messages.

