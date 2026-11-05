# User Guide

This guide describes the current local demonstration application. It does not describe a public production service.

## Open the application

Start the project using the root `README.md` Docker Compose instructions, then open `http://localhost:3000` in a browser. The API documentation is available at `http://localhost:8000/docs` while the backend is running.

## Ask a policy question

1. Open the chat page.
2. Ask a question about the Kenya Airways policy documents that staff have uploaded.
3. Read the answer and its listed source documents. If the answer says the documents do not cover the topic, use the official Kenya Airways link provided by the assistant or ask staff to add an appropriate source.
4. For booking, flight status, check-in, or booking management, follow the official Kenya Airways handoff link. This application does not make or change a booking and does not provide live flight status or fares.

Guest chat is available without signing in. Sign in as a passenger to retain and revisit conversation history.

## Passenger account and saved trips

Passengers can register or sign in through the passenger login flow. Auth0-based sign-in is available when the operator has configured its application settings and credentials.

From **My trips**, a signed-in passenger can save an itinerary and add, complete, or remove reminders. A reminder is an organizational aid; it does not verify a flight or booking. Do not enter a booking reference, passport information, or payment details into chat or trip notes.

## Staff workspace

Staff sign in at `/staff/login`; staff accounts are created by an administrator and cannot self-register. Staff can:

- Upload policy source files in PDF or HTML format and inspect the indexed document list.
- View their own saved conversation history in the chat workspace.
- Use **Manage staff** only if signed in as the administrator.

Only upload files that the project team is permitted to use. Check the source URL, locale, and version before relying on an uploaded policy document.

## Administrator setup

The first administrator is created through `/staff/setup` using the one-time `ADMIN_SETUP_TOKEN` configured by the operator. Remove that secret from the environment after setup. Administrators create policy staff accounts from **Manage staff**. Share initial credentials privately and ask staff to use a unique password.

## If something goes wrong

- **The page cannot reach the API:** confirm the backend is running and `NEXT_PUBLIC_API_URL` points to an address reachable from the browser.
- **Sign-in fails:** confirm the correct passenger or staff sign-in page is being used; check the backend logs without sharing tokens or passwords.
- **An answer lacks the expected policy detail:** verify the relevant file appears in the staff document list and re-index or upload the corrected source. The answer quality depends on source coverage and retrieval.
- **A reminder email does not arrive:** in-app reminders are separate from email delivery; email requires a valid backend mail-provider configuration.

## Current limitations

The application does not book, change, or cancel flights. It has no verified live KQ flight offers or flight status. Reminders do not monitor a flight. The local demo setup is not a hosted service and has no documented production support or uptime guarantee.
