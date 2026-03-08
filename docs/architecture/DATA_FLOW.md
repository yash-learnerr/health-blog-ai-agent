## MyDrScripts Backend Data Flow

This document focuses on **how data moves through the system** rather than the static structure of the repository.

It is intended to help developers understand:

- request-to-response flow
- side-effect fan-out
- booking/payment lifecycle paths
- notification and realtime propagation
- cron and webhook driven flows
- AI/STT/medical note movement

## 1. Base Request Flow

### End-to-end request path

```mermaid
sequenceDiagram
    participant Client as Client
    participant Routes as config/routes.js
    participant Policy as Policy Layer
    participant Controller as Controller
    participant Service as Service
    participant Model as Model / DB
    participant Integration as External API

    Client->>Routes: HTTP request
    Routes->>Policy: route + policy resolution
    Policy->>Controller: authorized request
    Controller->>Service: business call
    Service->>Model: read/write
    Service->>Integration: optional external call
    Service-->>Controller: result
    Controller-->>Client: JSON response
```

### Main files in the path

- `config/routes.js`
- `config/policies.js`
- `api/policies/*`
- `api/controllers/*`
- `api/services/*`
- `api/models/*`

## 2. Auth Data Flow

### Authentication and access flow

```mermaid
flowchart LR
    LOGINREQ[Login / Protected Request] --> JWT[JwtService]
    JWT --> USER[Users model]
    USER --> POLICY[isAuthenticated]
    POLICY --> ROLE[isDoctor / isPatient / isAdmin]
    ROLE --> CTRL[Controller Action]
```

### Notes

- identity centers around `Users`
- JWT validation gates most protected flows
- admin flows may continue into `checkModulePermission`
- user context then drives downstream domain access

## 3. Booking Creation Flow

### Booking request lifecycle

```mermaid
flowchart TD
    PATIENT[Patient Client] --> ROUTE[Booking Route]
    ROUTE --> CTRL[Booking Controller / Action]
    CTRL --> BOOK[BookingService]
    BOOK --> USER[Users / Patient data]
    BOOK --> DOC[Doctor data / service data]
    BOOK --> PRICE[Pricing logic]
    BOOK --> PB[(Patient_Booking)]
    BOOK --> DETAILS[Booking detail records]
    BOOK --> FILES[Booking files if needed]
    BOOK --> NOTIF[Notification side effects]
    BOOK --> RESP[API Response]
```

### Main code touchpoints

- `api/services/BookingService.js`
- `api/models/Patient_Booking.js`
- `api/controllers/booking/*`

### Data written during booking-related flows

- booking row
- optional booking detail rows
- audit/log rows
- file attachments
- downstream notification records

## 4. Booking State Transition Flow

### Runtime + background transitions

```mermaid
flowchart TD
    CREATE[Booking Created] --> PAYSTATE[Payment State]
    PAYSTATE --> WAIT[Waiting Room / Upcoming]
    WAIT --> CONSULT[Consultation Active]
    CONSULT --> COMPLETE[Completed]
    PAYSTATE --> CANCEL[Cancelled / Unpaid / Expired]

    CRON[CronService] --> WAIT
    CRON --> CANCEL
    CRON --> COMPLETE
```

### Why this matters

Booking state is not managed only by synchronous APIs.

It can also be affected by:

- webhooks
- cron jobs
- payment success/failure callbacks
- doctor/patient actions

## 5. Payment and Stripe Data Flow

### Payment lifecycle

```mermaid
sequenceDiagram
    participant Client as Client
    participant Ctrl as Booking/Payment Controller
    participant StripeSvc as StripeService
    participant Stripe as Stripe API
    participant DB as Booking/Payment Models
    participant Webhook as WebhookController

    Client->>Ctrl: request payment URL/session
    Ctrl->>StripeSvc: create checkout/session
    StripeSvc->>Stripe: create external payment object
    Stripe-->>StripeSvc: checkout/session payload
    StripeSvc-->>Ctrl: URL / metadata
    Ctrl-->>Client: payment response

    Stripe->>Webhook: webhook event
    Webhook->>StripeSvc: verify/process event
    StripeSvc->>DB: persist final payment outcome
```

### Main files

- `api/services/StripeService.js`
- `api/controllers/WebhookController.js`
- booking/payment controllers and models
- `config/http.js` for webhook raw-body handling

### Side effects after successful payment

- booking payment state update
- wallet/membership/referral adjustments
- notifications
- downstream consultation readiness

## 6. Wallet / Referral / Membership Flow

```mermaid
flowchart LR
    BOOK[Booking] --> DISC[Discount / Credit Evaluation]
    DISC --> WAL[WalletService]
    DISC --> REF[ReferralService]
    DISC --> MEM[MembershipService]
    WAL --> FINAL[Final Charge / Adjustment]
    REF --> FINAL
    MEM --> FINAL
    FINAL --> STRIPE[StripeService]
```

### Main idea

Final booking cost is not always just service price.

It may depend on:

- wallet credit
- referral incentive state
- membership discount logic
- Stripe success/failure outcome

## 7. Notification Flow

### Event fan-out path

```mermaid
flowchart TD
    EVENT[Business Event] --> NS[NotificationService]
    NS --> DB[(Notifications)]
    NS --> SOCKET[SocketService]
    NS --> PUSH[FirebaseService]
    NS --> MAIL[MailService]
    NS --> SMS[SmsService]
```

### Event sources commonly feeding notifications

- booking creation/update/cancel
- payment state changes
- reminders
- communication campaigns
- admin or doctor actions

## 8. Realtime Socket Flow

### Connection flow

```mermaid
sequenceDiagram
    participant Client as Socket Client
    participant Connect as api/controllers/socket/connect.js
    participant Auth as auth lookup
    participant GS as Group_Sockets
    participant Room as Rooms

    Client->>Connect: connect
    Connect->>Auth: verify identity
    Connect->>GS: insert/update socket mapping
    Connect->>Room: join user/group rooms
```

### Message / event delivery flow

```mermaid
flowchart LR
    APP[App Event] --> SS[SocketService]
    SS --> USERROOM[User room]
    SS --> GROUPROOM[Group room]
    USERROOM --> CLIENT[Connected clients]
    GROUPROOM --> CLIENT
```

## 9. Communication Campaign Flow

### Campaign processing path

```mermaid
flowchart TD
    ADMIN[Admin Action] --> COMMCTRL[Communication Controllers]
    COMMCTRL --> COMMSVC[CommunicationService]
    COMMSVC --> GROUPS[Recipient Groups]
    COMMSVC --> TPL[Templates]
    COMMSVC --> CONSENT[Consent Filtering]
    COMMSVC --> RECIP[Campaign Recipient Records]
    COMMSVC --> SEND[Email / Notification Delivery]
```

### Async execution note

Campaigns are not only request-driven.

They can also be picked up and processed by cron jobs for delayed or batched delivery.

## 10. File Upload and Retrieval Flow

### Storage path

```mermaid
flowchart LR
    CLIENT[Upload Request] --> CTRL[Controller]
    CTRL --> FILESVC[FileService]
    FILESVC --> STORAGE[DigitalOcean Spaces]
    STORAGE --> URL[Signed/Public URL]
    URL --> CLIENT
```

### Typical file categories

- doctor documents
- patient documents
- booking attachments
- generated artifacts or PDFs
- AI/STT assets where applicable

## 11. AI Chat Flow

### AI service-discovery style flow

```mermaid
flowchart TD
    USER[Client Prompt] --> AICHAT[AiChatController]
    AICHAT --> OA[OpenAIService]
    OA --> SERVICES[Visible service data / business grounding]
    OA --> OPENAI[OpenAI API]
    OPENAI --> OA
    OA --> RESP[Structured AI response]
    RESP --> USER
```

### Main idea

The AI layer is not just generic prompting. It appears to use live service/domain data to ground responses for the product.

## 12. AI Talk / Voice Flow

```mermaid
flowchart TD
    CLIENT[Voice Client] --> TALKCTRL[AiTalkController]
    TALKCTRL --> TALKSVC[AiTalkService]
    TALKSVC --> ELEVEN[ElevenLabs]
    TALKSVC --> SESSION[Session State]
    SESSION --> CLIENT
```

### Purpose

- create/manipulate voice AI sessions
- return signed/session-aware payloads to frontend
- mediate tool execution through controlled service logic

## 13. STT and Medical Notes Flow

### Transcript to notes path

```mermaid
flowchart TD
    CALL[Consultation / Audio] --> STTCTRL[AgoraSttController]
    STTCTRL --> AGORA[Agora STT]
    AGORA --> SESS[(Stt_Sessions)]
    AGORA --> TRANS[(Stt_Transcripts)]
    TRANS --> SCRIBE[MedicalScribeService]
    SCRIBE --> OPENAI[OpenAIService / OpenAI]
    OPENAI --> NOTES[Structured Medical Notes]
    NOTES --> MNCTRL[MedicalNotesController]
    MNCTRL --> DB[(Notes / related storage)]
```

### Main files

- `api/controllers/AgoraSttController.js`
- `api/services/MedicalScribeService.js`
- `api/controllers/MedicalNotesController.js`
- `api/models/Stt_Sessions.js`
- `api/models/Stt_Transcripts.js`

## 14. Healthcare Integration Flow

### External clinical integration pattern

```mermaid
flowchart LR
    CLIENT[Controller Request] --> SERVICE[MedicareService / MimsService / ErxService]
    SERVICE --> AUTH[certs / tokens / credentials]
    AUTH --> EXT[Healthcare External System]
    EXT --> SERVICE
    SERVICE --> DB[(logs / audit / domain records)]
    SERVICE --> CLIENT
```

### Main pattern seen in codebase

- controller receives request
- service prepares auth or XML/token payloads
- outbound integration is called
- result is logged and/or persisted
- domain entity is updated or response returned

## 15. Cron-Driven Flow

### Scheduled execution path

```mermaid
flowchart TD
    SCHEDULE[config/cron.js] --> HOOK[sails-hook-cron]
    HOOK --> CRON[CronService]
    CRON --> BOOK[Booking tasks]
    CRON --> REM[Reminder tasks]
    CRON --> COMM[Campaign tasks]
    CRON --> TOKEN[External token refresh]
    CRON --> CLEAN[Cleanup tasks]
```

### Important implication

Some system state changes happen **without an incoming API request**.

When debugging a record mutation, check:

- user action
- webhook action
- cron action

## 16. Logging Flow

### Error/event persistence path

```mermaid
flowchart LR
    APP[Error or Domain Event] --> LOG[LogService]
    LOG --> CONSOLE[Console]
    LOG --> DB[(Persisted log tables)]
```

### Debugging implication

Operational context may exist in:

- runtime logs
- database log tables
- booking audit records
- integration-specific logs

## 17. Recommended Debugging Flow

When tracing unexpected behavior, use this order:

1. find the route in `config/routes.js`
2. confirm policies in `config/policies.js`
3. open controller/action
4. follow service calls
5. inspect touched models
6. check for:
   - webhook involvement
   - cron involvement
   - socket/notification side effects
   - external integration responses
   - persisted logs

## 18. Final Flow Summary

```mermaid
flowchart TD
    REQ[Request / Event] --> ROUTE[Routes or Cron or Webhook]
    ROUTE --> POLICY[Policies if request-driven]
    POLICY --> CTRL[Controller / Entry Action]
    CTRL --> SERVICE[Service Layer]
    SERVICE --> DB[(MySQL)]
    SERVICE --> EXT[External APIs]
    SERVICE --> SIDE[Notifications / Files / Sockets / Logs]
    SIDE --> CLIENTS[Users / Admins / Devices]
```

**The most important architectural fact about data flow in this system is that business state can change through three paths: request handlers, webhooks, and cron jobs.**