# FastShip Frontend Guide: React + FastAPI

Open this file in VS Code and press **Cmd + Shift + V** to read it as a formatted page.

Everything here was built and tested before you got it. That includes the backend tests, the TypeScript build, the linter, and a real browser that clicked through every page, including scanning the QR code from the delivery email with a camera. Part 12 has the details.

## How to use this guide

- Do the parts **in order**. Each step tells you **what** to do, then **why**.
- **"Replace the whole file"** means select everything in the file (Cmd + A), then paste the new code. **"Create"** means make a new file at that path.
- The **project root** is the folder with `app/` and `pyproject.toml`. **`frontend/`** is the new folder we create inside it.
- If any step gives an error, stop and send me the error.
- Don't skip the explanations. They're the part you're learning.

---

## What we're building

| Page (URL) | Who | What it does | API endpoints it uses |
|---|---|---|---|
| `/` | Everyone | Landing page, track a shipment by id | none |
| `/login` | Everyone | Log in as a seller or a partner | `POST /seller/token`, `POST /partner/token` |
| `/signup` | Everyone | Create an account, then log in | `POST /seller/signup`, `POST /partner/signup` |
| `/track/:id` | The client (public) | Status, details and timeline | `GET /shipment/` |
| `/seller` | Sellers | Stats, list, status and tag filters | `GET /seller/shipments` **(new)**, `GET /tag/`, `GET /tag/shipments`, `GET /seller/me` **(new)** |
| `/seller/shipments/new` | Sellers | Create a shipment | `POST /shipment/` |
| `/seller/shipments/:id` | Sellers | Details, add and remove tags, cancel, copy the tracking link | `GET /shipment/`, `POST /shipment/tag`, `DELETE /shipment/tag`, `POST /shipment/cancel` |
| `/partner` | Partners | Assigned shipments, capacity used | `GET /partner/shipments` **(new)**, `GET /partner/me` **(new)** |
| `/partner/shipments/:id` | Partners | Update progress, confirm delivery by typing or **scanning the QR code**, send a new code | `PATCH /shipment/`, `POST /shipment/verify`, `POST /shipment/resend-code` |
| `/partner/profile` | Partners | Zip codes and capacity | `GET /partner/me`, `PATCH /partner/` |
| Sidebar user menu | Both | Log out | `GET /seller/logout`, `GET /partner/logout` |

These endpoints have no React page, on purpose:
- `GET /shipment/track` is the backend's own HTML tracking page, and the links in the emails still open it. The React page `/track/:id` shows the same information.
- `GET /shipment/cancel` is deprecated. The frontend uses `POST /shipment/cancel`.
- `/time`, `/file`, `/timenow`, `/utcnow` and `/custom` are course demos, not part of FastShip.

## The tools, and why each one

| Tool | What it does | Notes |
|---|---|---|
| **Vite 8** | Development server and production build | Same as the course |
| **React 19 + TypeScript 7** | The UI library, plus types | TypeScript catches mistakes before you run anything, and the API types are generated for us |
| **Tailwind CSS 4** | Styling with classes like `flex gap-4 p-6` | shadcn needs it |
| **shadcn/ui** (built on Radix) | Ready components **copied into your project**, so you own and can edit the code | Same as the course. We also use 3 ready "blocks": a login page, a signup page and a sidebar |
| **React Router 8** | Shows a page for each URL | The course probably used `react-router-dom`. **That package was removed in v8**, so everything now comes from `react-router` |
| **TanStack Query** (React Query) | Fetches, caches and refreshes API data | Same as the course (`QueryClientProvider`) |
| **axios + swagger-typescript-api** | A typed API client **generated** from FastAPI's `/openapi.json` | Same as the course, plus a backend change for readable method names |
| **react-hook-form + zod** | Forms and validation | The most common pair in React apps |
| **sonner** | Toast notifications | shadcn's old "toast" component was replaced by sonner |
| **@yudiel/react-qr-scanner** | Scans QR codes with a PC or phone camera | The older `react-qr-reader` is unmaintained and doesn't support React 19 |
| **localStorage + React Context** | Keeps the login session | No Redux or Zustand needed, see below |

**Two kinds of state.** This is the most important idea in frontend architecture:
- **Server state** is data that lives in the database: shipments, profile, tags. React Query owns it. It fetches it, caches it, and refetches it when it may be old.
- **Client state** is data that lives only in the browser. Here it's just "who is logged in" (the token and the role). A small React Context holds it.

That's why we don't need Redux or Zustand. Many older tutorials put API data in Redux, but that's the job React Query does better.

## How the pieces talk to each other

```
Browser: React app on http://localhost:5173
   │  axios calls /api/seller/shipments  with header  Authorization: Bearer <token>
   ▼
Vite dev server  ── proxy removes "/api" ──►  FastAPI on http://localhost:8000/seller/shipments
                                                  │
                         Postgres · Redis · RabbitMQ → Celery worker → email with a QR code
```

**Why the proxy?** The browser thinks it's talking to the same address (`localhost:5173`), so CORS isn't involved during development. It also makes phone testing work over HTTPS (Part 10). In production, a web server like nginx does the same job, or you set `VITE_API_URL` and use the CORS settings you already built.

---

# Part 1: Backend changes

The frontend needs four things the API doesn't have yet:
1. **Readable names for the generated client.**
2. **"Who am I?"** (`/seller/me`, `/partner/me`), so the sidebar can show your name and the profile form can be filled in.
3. **"My shipments"** (`/seller/shipments`, `/partner/shipments`). Without them, a dashboard has nothing to list.
4. **A QR code in the delivery email**, so the partner can scan it instead of typing the code.

## 1.1 Readable operation ids

FastAPI gives every endpoint an **operation id** in `/openapi.json`. By default it's long, like `get_shipment_shipment__get`. swagger-typescript-api turns each id into a method name, so we'd get `api.shipment.getShipmentShipmentGet()`. We'll use the function name instead, which gives `api.shipment.getShipment()`.

In [app/api/docs.py](../app/api/docs.py), add this import under `from fastapi.openapi.models import Example`:
```python
from fastapi.routing import APIRoute
```
Add this at the **end** of the file:
```python
def operation_id(route: APIRoute) -> str:
    # Name each endpoint after its function, e.g. get_shipment instead of
    # get_shipment_shipment__get, so the generated frontend client is readable
    return route.name
```
In [app/main.py](../app/main.py), change the import:
```python
from app.api.docs import DESCRIPTION, TAGS_METADATA, operation_id
```
In `FastAPI(...)`, add this line under `openapi_tags=TAGS_METADATA,`:
```python
    generate_unique_id_function=operation_id,
```
This works only because every route function has a unique name. A test in 1.4 makes sure that stays true.

## 1.2 "Who am I" and "my shipments"

In [app/services/shipment.py](../app/services/shipment.py), make the top imports look like this. Three lines are new: `Sequence`, `select` and `col`.
```python
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col
```
Add these two methods under the `get` method:
```python
    async def get_by_seller(self, seller: Seller) -> Sequence[Shipment]:
        # Newest first, for the seller's dashboard
        return (
            await self.session.scalars(
                select(Shipment)
                .where(col(Shipment.seller_id) == seller.id)
                .order_by(col(Shipment.created_at).desc())
            )
        ).all()

    async def get_by_partner(self, partner: DeliveryPartner) -> Sequence[Shipment]:
        return (
            await self.session.scalars(
                select(Shipment)
                .where(col(Shipment.delivery_partner_id) == partner.id)
                .order_by(col(Shipment.created_at).desc())
            )
        ).all()
```
**Why a query with `order_by`?** The database sorts faster than Python, and the order is guaranteed.

In [app/api/routers/seller.py](../app/api/routers/seller.py), replace the `..dependencies` import and add the `ShipmentRead` import:
```python
from ..dependencies import (
    SellerDep,
    SellerServiceDep,
    ShipmentServiceDep,
    get_seller_access_token,
)
from ..docs import errors
from ..schemas.common import Message, Token
from ..schemas.seller import SellerCreate, SellerRead
from ..schemas.shipment import ShipmentRead
```
Add these two endpoints **above** the `/logout` endpoint:
```python
@router.get(
    "/me",
    response_model=SellerRead,
    summary="The logged in seller",
    responses=errors(401),
)
async def get_seller_profile(seller: SellerDep):
    """The frontend uses it to show who is logged in."""
    return seller


@router.get(
    "/shipments",
    response_model=list[ShipmentRead],
    summary="My shipments",
    responses=errors(401),
)
async def get_seller_shipments(seller: SellerDep, service: ShipmentServiceDep):
    """Every shipment the logged in seller created, newest first."""
    return await service.get_by_seller(seller)
```
In [app/api/routers/delivery_partner.py](../app/api/routers/delivery_partner.py), add `ShipmentServiceDep` to the `..dependencies` import:
```python
from ..dependencies import (
    DeliveryPartnerDep,
    DeliveryPartnerServiceDep,
    ShipmentServiceDep,
    get_partner_access_token,
)
```
Under the `..schemas.delivery_partner import (...)` block, add:
```python
from ..schemas.shipment import ShipmentRead
```
Add these two endpoints **above** the `@router.patch("/", ...)` endpoint:
```python
@router.get(
    "/me",
    response_model=DeliveryPartnerRead,
    summary="The logged in partner",
    responses=errors(401),
)
async def get_partner_profile(partner: DeliveryPartnerDep):
    """The frontend uses it to show who is logged in and fill the profile form."""
    return partner


@router.get(
    "/shipments",
    response_model=list[ShipmentRead],
    summary="My assigned shipments",
    responses=errors(401),
)
async def get_partner_shipments(
    partner: DeliveryPartnerDep,
    service: ShipmentServiceDep,
):
    """Every shipment assigned to the logged in partner, newest first."""
    return await service.get_by_partner(partner)
```
**Why `response_model=SellerRead` and not the database model?** `SellerRead` doesn't contain `password_hash`. The response model decides exactly which fields leave the server.

## 1.3 A QR code in the delivery email

When a shipment goes **out for delivery**, the Celery worker emails the client a 6-digit code. Now the email will also contain that code as a QR image, which the partner can scan with the app.

**How it works:**
- **The QR image is made on our server** with the `segno` library. An online QR service would see the code, which would leak a secret.
- **The image is attached "inline"** with a **Content-ID** (`cid`). The HTML then shows it with `<img src="cid:delivery_code">`. Gmail and most email apps block images written straight into the HTML (`data:` URLs), but they show `cid` images.
- **My first version had a bug, found by the browser test.** `segno.make()` chooses a **Micro QR** for short text like `123456`. A Micro QR has only one corner square, and browsers can't read it. `segno.make_qr()` always makes a normal QR code.

In the project root, with your `.venv` active:
```bash
pip install segno
pip freeze > requirements.txt
```
In [pyproject.toml](../pyproject.toml), add `"segno",` to the `dependencies` list, after `"flower==2.2.0"`. Remember to put a comma after `"flower==2.2.0"`.

In [app/worker/tasks.py](../app/worker/tasks.py), replace the imports at the top, down to the `from app...` lines, with these. New: `BytesIO`, `segno`, `MultipartSubtypeEnum`, `Headers` and `UploadFile`.
```python
import asyncio
import logging
from datetime import UTC, datetime
from io import BytesIO

import segno
from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from fastapi_mail.errors import ConnectionErrors
from fastapi_mail.schemas import MultipartSubtypeEnum
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool
from sqlmodel import col
from starlette.datastructures import Headers, UploadFile
from twilio.base.exceptions import TwilioException  # type: ignore[import-untyped]
from twilio.http.http_client import TwilioHttpClient  # type: ignore[import-untyped]
from twilio.rest import Client  # type: ignore[import-untyped]
```
Replace the whole `_send_template_email` function, and add `_qr_code_image` right after it:
```python
def _send_template_email(
    recipients: list[str],
    subject: str,
    context: dict,
    template_name: str,
    attachments: list[UploadFile | dict | str] | None = None,
):
    # fastapi-mail is async and tasks are not, so asyncio.run bridges them
    asyncio.run(
        fastmail.send_message(
            MessageSchema(
                recipients=recipients,  # type: ignore[arg-type]
                subject=subject,
                template_body=context,
                subtype=MessageType.html,
                attachments=attachments or [],
                # "related" lets the HTML show attached images with <img src="cid:...">
                multipart_subtype=MultipartSubtypeEnum.related,
            ),
            template_name=template_name,
        )
    )


def _qr_code_image(text: str, content_id: str) -> dict:
    # A PNG QR code, attached inline so email apps show it inside the message.
    # It's made here because sending the code to an online QR service would leak it
    image = BytesIO()
    # make_qr, not make: for short text make() picks a Micro QR, which most
    # scanners (and browsers) can't read
    segno.make_qr(text, error="m").save(image, kind="png", scale=8, border=2)
    image.seek(0)

    return {
        "file": UploadFile(
            file=image,
            filename="delivery-code.png",
            headers=Headers({"content-type": "image/png"}),
        ),
        "headers": {
            "Content-ID": f"<{content_id}>",
            "Content-Disposition": 'inline; filename="delivery-code.png"',
        },
        "mime_type": "image",
        "mime_subtype": "png",
    }
```
At the end of `send_verification_code`, add the `attachments=` line to the `_send_template_email(...)` call:
```python
    _send_template_email(
        [email],
        "Your Order is Arriving Soon 🛵",
        {"code": code},
        "mail_out_for_delivery.html",
        # The partner can scan it instead of typing the code
        attachments=[_qr_code_image(code, "delivery_code")],
    )
```
**Why `UploadFile` from Starlette and not from FastAPI?** fastapi-mail's types expect Starlette's class. FastAPI's `UploadFile` is a subclass of it, and Mypy reports an error if you use that one.

In [app/templates/mail_out_for_delivery.html](../app/templates/mail_out_for_delivery.html), add the two new lines under the "Your delivery code is" line, inside the `{% if code %}` block:
```html
    <p>Your delivery code is <strong>{{ code }}</strong>. Share it only with the delivery partner when you receive your shipment.</p>
    <p>The delivery partner can also scan this code:</p>
    <img src="cid:delivery_code" alt="Delivery code {{ code }}" width="200" height="200">
```
The SMS path (Twilio) stays text only, because an SMS can't carry an image.

## 1.4 Tests for the new code

Every new endpoint gets tests, the same practice as the regression test for `cancel`.

Create `tests/api/test_accounts.py`:
```python
from httpx import AsyncClient

from tests.helpers import ZIP_CODE, login


async def test_seller_profile(client: AsyncClient, seller, seller_headers):
    response = await client.get("/seller/me", headers=seller_headers)

    assert response.status_code == 200
    assert response.json()["email"] == seller.email


async def test_partner_profile(client: AsyncClient, partner, partner_headers):
    response = await client.get("/partner/me", headers=partner_headers)

    assert response.status_code == 200
    assert response.json()["serviceable_zip_codes"] == [ZIP_CODE]


async def test_profiles_need_login(client: AsyncClient):
    assert (await client.get("/seller/me")).status_code == 401
    assert (await client.get("/partner/me")).status_code == 401


async def test_seller_shipments_newest_first(
    client: AsyncClient, seller_headers, partner, shipment_data
):
    first = await client.post("/shipment/", json=shipment_data, headers=seller_headers)
    second = await client.post("/shipment/", json=shipment_data, headers=seller_headers)

    response = await client.get("/seller/shipments", headers=seller_headers)

    assert response.status_code == 200
    ids = [shipment["id"] for shipment in response.json()]
    assert ids == [second.json()["id"], first.json()["id"]]


async def test_seller_sees_only_own_shipments(
    client: AsyncClient, shipment, make_seller
):
    other = await make_seller("other@example.com")
    other_headers = await login(client, "seller", other.email)

    response = await client.get("/seller/shipments", headers=other_headers)

    assert response.json() == []


async def test_partner_shipments(client: AsyncClient, shipment, partner_headers):
    response = await client.get("/partner/shipments", headers=partner_headers)

    assert response.status_code == 200
    assert [s["id"] for s in response.json()] == [shipment["id"]]
```
Create `tests/unit/test_openapi.py`:
```python
from app.main import app


def test_operation_ids_are_unique():
    # The frontend client gets one method per operation id, so each must be unique
    operations = [
        operation["operationId"]
        for path in app.openapi()["paths"].values()
        for operation in path.values()
    ]

    assert len(operations) == len(set(operations))
    assert "get_shipment" in operations
```
Create `tests/unit/test_email.py`:
```python
from app.worker.tasks import _qr_code_image


def test_qr_code_is_an_inline_png():
    attachment = _qr_code_image("123456", "delivery_code")

    # The template shows it with <img src="cid:delivery_code">
    assert attachment["headers"]["Content-ID"] == "<delivery_code>"
    assert attachment["headers"]["Content-Disposition"].startswith("inline")
    assert attachment["file"].file.read().startswith(b"\x89PNG")
```

## 1.5 Check the backend
In the project root:
```bash
pytest
ruff check app tests
mypy app tests        # or the VS Code Mypy panel
```
You should get **79 passed** (71 old plus 8 new), and Ruff and Mypy should show no errors.

**Restart the Celery worker** (Ctrl+C, then start it again). A running worker keeps using the old code until it restarts.

Open http://localhost:8000/scalar. You'll see the 4 new endpoints, and the operation names are now short.

---

# Part 2: Create the React app

## 2.1 Check your tools
```bash
node -v      # v26.x (anything from v22 works)
npm -v       # 11.x
echo $NODE_ENV
```
`echo $NODE_ENV` must print **an empty line**. If it prints `production`, npm skips every development package, like TypeScript and the Vite React plugin, and the build fails. My tool environment had this set. If yours does too, run `unset NODE_ENV` in that terminal.

## 2.2 Create the project
In the **project root**:
```bash
npm create vite@9.3.4 frontend -- --template react-ts --no-immediate --no-interactive
cd frontend
npm install
```
**What these mean:**
- **`frontend`** is the folder name. Having it next to `app/` is the common layout for one repository that holds the backend and frontend together.
- **`--template react-ts`** means React with TypeScript.
- **`--no-immediate`** means don't start the server yet.
- **`--no-interactive`** means use these answers instead of asking questions.
- **`@9.3.4`** pins the exact version I tested. Normally you'd write `@latest`.
- **`npm install`** downloads the packages listed in `package.json` into `node_modules/`. The `.gitignore` that Vite created keeps that folder out of git.

You may see `npm warn allow-scripts ... fsevents`. That's harmless. npm 11 blocks install scripts by default for safety, and `fsevents` is an optional macOS file watcher that we don't need.

**Try it:** run `npm run dev` and open http://localhost:5173. You'll see the Vite + React demo page. Press **Ctrl + C** to stop it.

### What Vite created, and React basics
| File | What it is |
|---|---|
| `index.html` | The only HTML page. It has an empty `<div id="root">` and loads `src/main.tsx` |
| `src/main.tsx` | Starts React and draws the app into `#root` |
| `package.json` | The project's packages and scripts (`npm run dev`, `npm run build`) |
| `package-lock.json` | The exact installed versions. Commit it, so everyone gets the same versions |
| `tsconfig*.json` | TypeScript settings. Strict by default, which is good |
| `vite.config.ts` | Vite settings: plugins, the API proxy, aliases |
| `.oxlintrc.json` | Linter settings. Oxlint is Vite's new default linter, a very fast ESLint alternative |

**React in 6 ideas.** You'll see all of them in the code below.
1. **A component is a function that returns JSX.** JSX is HTML-like syntax inside TypeScript: `function Logo() { return <a>FastShip</a> }`. Component names start with a capital letter.
2. **Props are a component's inputs:** `<StatusBadge status="delivered" />`. The component receives `{ status }`.
3. **State is data that changes:** `const [code, setCode] = useState("")`. Calling `setCode` makes React draw the component again with the new value.
4. **Hooks are functions starting with `use`** (`useState`, `useQuery`, `useForm`, `useNavigate`). Call them only at the top of a component, never inside an `if` or a loop.
5. **Children:** whatever you put between a component's opening and closing tags arrives as `children`. `<Card>...</Card>` works this way.
6. **Lists need a `key`:** `shipments.map((s) => <TableRow key={s.id}>...)`. The key lets React tell the rows apart.

## 2.3 Tailwind CSS
In `frontend/`:
```bash
npm install tailwindcss @tailwindcss/vite
```
Replace the whole of `frontend/src/index.css` with this one line (shadcn adds more to it in 2.5):
```css
@import "tailwindcss";
```
**Why:** with Tailwind, you style elements with classes in the JSX, like `className="flex gap-4 p-6"`, instead of separate CSS files. Tailwind 4 needs only this one import plus the Vite plugin.

## 2.4 The `@/` import alias
Without an alias, deep files need imports like `../../components/ui/button`. With it, every file writes `@/components/ui/button`.

Replace the whole of `frontend/tsconfig.json`:
```json
{
  "files": [],
  "references": [
    { "path": "./tsconfig.app.json" },
    { "path": "./tsconfig.node.json" }
  ],
  "compilerOptions": {
    "paths": {
      "@/*": ["./src/*"]
    }
  }
}
```
Replace the whole of `frontend/tsconfig.app.json`:
```json
{
  "compilerOptions": {
    "tsBuildInfoFile": "./node_modules/.tmp/tsconfig.app.tsbuildinfo",
    "target": "es2023",
    "lib": ["ES2023", "DOM"],
    "module": "esnext",
    "types": ["vite/client"],
    "allowArbitraryExtensions": true,
    "skipLibCheck": true,

    /* Bundler mode */
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "verbatimModuleSyntax": true,
    "moduleDetection": "force",
    "noEmit": true,
    "jsx": "react-jsx",

    /* Linting */
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "erasableSyntaxOnly": true,
    "noFallthroughCasesInSwitch": true,

    /* Lets imports start with @/ instead of ../../ */
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["src"]
}
```
The shadcn docs also add `"baseUrl": "."`. **Don't add it.** TypeScript 7 removed `baseUrl`, and `paths` works without it.

Replace the whole of `frontend/vite.config.ts`. This is a temporary version, and 2.9 gives the final one:
```ts
import path from "path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
})
```
TypeScript needs the alias to check types, and Vite needs it to load the files. That's why it's set in two places.

## 2.5 shadcn/ui
In `frontend/`:
```bash
npx shadcn@4.23.0 init -b radix -p nova --no-monorepo
```
- **`-b radix`** builds the components on Radix, which most tutorials and examples use.
- **`-p nova`** is the default look, using the Lucide icon set and the Geist font.

**What it did:**
- **`components.json`** is shadcn's settings, including where to put components.
- **`src/lib/utils.ts`** has the `cn()` helper, which merges class names.
- **`src/index.css`** got the theme colors, as CSS variables, plus dark mode support.
- **New packages:** `radix-ui`, `lucide-react` (icons), `cn` (shadcn's own small class-merge package), the Geist font and animation helpers.

**The big idea of shadcn:** it's not a package you import from `node_modules`. It **copies the component source code into `src/components/ui/`**. The code is yours. You can read it and change it, and there's no version lock-in. You usually don't need to edit those files.

## 2.6 Components and ready-made blocks
```bash
npx shadcn@4.23.0 add login-03 signup-03 sidebar-07 badge table dialog alert-dialog select tabs input-otp textarea skeleton sonner empty spinner -y
```
**The blocks are full designs copied into `src/components/`:**
- **`login-03`** is a login card on a gray background, in `login-form.tsx`.
- **`signup-03`** is the matching signup card, in `signup-form.tsx`.
- **`sidebar-07`** is a sidebar that collapses to icons, with a user menu at the bottom. It's split into `app-sidebar.tsx`, `nav-main.tsx`, `nav-user.tsx`, `nav-projects.tsx` and `team-switcher.tsx`.

**The components go into `src/components/ui/`:**

| Component | What we use it for |
|---|---|
| badge | Status and tag labels |
| table | Shipment lists |
| dialog | The QR scanner window |
| alert-dialog | "Cancel this shipment?" confirmation |
| select | Tag and status drop-downs |
| tabs | Seller/partner switch and the list filters |
| input-otp | The 6 boxes for the delivery code |
| textarea | The note field |
| skeleton | Gray placeholders while data loads |
| sonner | Toasts |
| empty | "Nothing here" states |
| spinner | Loading icon in buttons |

The blocks also pull in button, card, input, label, field, separator, sheet, tooltip, avatar, dropdown-menu, collapsible and breadcrumb. In total you should see **25 files in `src/components/ui/`**.

In 2.8 we delete the parts of the blocks we don't need. In Parts 6 and 7 we adapt the rest to FastShip. That's how blocks are meant to be used: start from a good design, then make it yours.

## 2.7 The other libraries
```bash
npm install react-router @tanstack/react-query @tanstack/react-query-devtools axios react-hook-form zod @hookform/resolvers @yudiel/react-qr-scanner
npm install -D swagger-typescript-api @vitejs/plugin-basic-ssl
```
`-D` means a **development dependency**: a tool that's only needed while building, not inside the app.

| Package | Role |
|---|---|
| `react-router` | URL → page |
| `@tanstack/react-query` | Server state (fetching and caching) |
| `@tanstack/react-query-devtools` | A panel to inspect the cache, development only |
| `axios` | HTTP client, used by the generated API client |
| `react-hook-form` | Form state and submission |
| `zod` | Validation rules (schemas) |
| `@hookform/resolvers` | Connects zod to react-hook-form |
| `@yudiel/react-qr-scanner` | The camera QR scanner |
| `swagger-typescript-api` (dev) | Generates `src/api/generated.ts` from `/openapi.json` |
| `@vitejs/plugin-basic-ssl` (dev) | HTTPS for testing on a phone |

`npm audit` will report 2 moderate issues inside the `shadcn` CLI package (`deepmerge` and `minimatch`). That code only runs when you use the shadcn command, never in the browser. **Don't run `npm audit fix --force`**, because it installs breaking versions.

## 2.8 Remove what we don't use
In `frontend/`:
```bash
rm -rf src/App.tsx src/App.css src/assets public/icons.svg src/components/team-switcher.tsx src/components/nav-projects.tsx
```
These are the Vite demo page and its images, plus the two sidebar-07 parts we don't use (a team switcher and a project list). Our app starts from `routes.tsx` instead of `App.tsx`.

## 2.9 Final config files

Replace the whole of `frontend/vite.config.ts`:
```ts
import path from "path"
import tailwindcss from "@tailwindcss/vite"
import basicSsl from "@vitejs/plugin-basic-ssl"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

// https://vite.dev/config/
export default defineConfig(({ mode }) => ({
  plugins: [
    react(),
    tailwindcss(),
    // `npm run dev:phone` uses HTTPS: phones only allow the camera on https://
    mode === "phone" && basicSsl(),
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    proxy: {
      // The browser calls /api/seller/me, Vite forwards it to FastAPI as /seller/me.
      // Same origin for the browser, so no CORS needed in development
      "/api": {
        target: "http://localhost:8000",
        rewrite: (url) => url.replace(/^\/api/, ""),
      },
    },
  },
}))
```
- **`proxy`** forwards `/api/...` to FastAPI, as in the diagram at the top.
- **`mode === "phone"`** turns on HTTPS only for `npm run dev:phone`. Browsers allow the camera only on `https://` or `localhost`. A phone opening `http://192.168.x.x` isn't either, so it needs HTTPS.

In `frontend/package.json`, replace the `"scripts"` block:
```json
  "scripts": {
    "dev": "vite",
    "dev:phone": "vite --host --mode phone",
    "build": "tsc -b && vite build",
    "lint": "oxlint",
    "preview": "vite preview",
    "api:generate": "swagger-typescript-api generate -p http://localhost:8000/openapi.json -o src/api -n generated.ts --axios --enum-style=union --type-only-imports --unwrap-response-data"
  },
```
In `frontend/index.html`, change `<title>frontend</title>` to:
```html
    <title>FastShip</title>
```
Replace the whole of `frontend/.oxlintrc.json`. It's a hidden file: in VS Code's explorer it shows normally, and in Finder press **Cmd + Shift + .** to see it.
```json
{
  "$schema": "./node_modules/oxlint/configuration_schema.json",
  "plugins": ["react", "typescript", "oxc"],
  "ignorePatterns": ["src/components/ui/**", "src/hooks/use-mobile.ts", "src/api/generated.ts"],
  "rules": {
    "react/rules-of-hooks": "error",
    "react/only-export-components": ["warn", { "allowConstantExport": true }]
  }
}
```
**Why `ignorePatterns`:** files we didn't write (shadcn's `ui/`, its `use-mobile` hook, the generated client) shouldn't fill the lint output with warnings we won't fix. Linting your own code is what matters.

---

# Part 3: Talking to the API

## 3.1 Generate the typed client
Start the backend in another terminal (project root, `fastapi dev`). Then, in `frontend/`:
```bash
npm run api:generate
```
This creates **`src/api/generated.ts`**, about 1,200 lines. **Don't type or edit it.** Regenerate it whenever the API changes.

**What's inside:**
- **TypeScript types for every schema:** `ShipmentRead`, `ShipmentCreate`, `TagName = "express" | "fragile" | ...` and so on.
- **An `Api` class with one method per endpoint:** `api.shipment.getShipment({ id })`, `api.seller.loginSeller(form)`, `api.partner.getPartnerShipments()` and so on.
- **Login secrecy built in:** each method knows whether its endpoint needs a login (`secure: true`), because FastAPI's OpenAPI says so.

**The flags:**
- **`--axios`** uses axios, so we can add interceptors.
- **`--enum-style=union`** makes enums plain string types. Vite's TypeScript setting `erasableSyntaxOnly` doesn't allow TypeScript `enum`.
- **`--type-only-imports`** is needed by the `verbatimModuleSyntax` setting.
- **`--unwrap-response-data`** makes methods return the data directly, not the whole axios response.

**Best practice:** commit `generated.ts`. Then the frontend builds without a running backend, and code reviews show exactly how the API changed.

**The biggest benefit:** if the backend renames a field, regenerate and run `npm run build`. TypeScript then lists every place in the frontend that breaks, before any user sees it.

## 3.2 The session in localStorage
Create `frontend/src/auth/session.ts`:
```ts
export type Role = "seller" | "partner"

export interface Session {
  token: string
  role: Role
}

const STORAGE_KEY = "fastship.session"

// localStorage keeps the session after a page refresh or closing the tab
export function getSession(): Session | null {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    return saved ? (JSON.parse(saved) as Session) : null
  } catch {
    // Broken or blocked storage: treat it as logged out
    return null
  }
}

export function saveSession(session: Session) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(session))
}

export function clearSession() {
  localStorage.removeItem(STORAGE_KEY)
}
```
**Where to keep the token, and the trade-off:**
- **localStorage**, which the course uses and we use too, is simple, survives a refresh, and works with our `Authorization: Bearer` API. The risk is that if the site ever had an XSS bug (injected JavaScript), that script could read the token.
- **An httpOnly cookie** can't be read by JavaScript, so it's safer against XSS. It needs backend changes (setting cookies, CSRF protection, `allow_credentials` in CORS).

For this project localStorage is fine and very common. React escapes all text by default, which already blocks most XSS.

## 3.3 The API client
Create `frontend/src/api/client.ts`:
```ts
import axios from "axios"

import { Api } from "@/api/generated"
import { clearSession, getSession } from "@/auth/session"

// In development Vite forwards /api to FastAPI (see vite.config.ts).
// If the API runs somewhere else, set VITE_API_URL in frontend/.env
const baseURL = import.meta.env.VITE_API_URL ?? "/api"

export const api = new Api({
  baseURL,
  // Runs before every request that needs a login (marked "secure" in the client)
  securityWorker: () => {
    const session = getSession()
    if (session) {
      return { headers: { Authorization: `Bearer ${session.token}` } }
    }
  },
})

// One place handles an expired or logged out token, for every request
api.instance.interceptors.response.use(undefined, (error) => {
  const sentToken = axios.isAxiosError(error) && error.config?.headers.Authorization
  if (sentToken && error.response?.status === 401) {
    clearSession()
    window.location.assign("/login?expired=1")
  }
  return Promise.reject(error)
})
```
- **`securityWorker`** runs before every `secure` request and adds the `Authorization` header. One place, instead of every call.
- **The interceptor** runs after every response. A **401 on a request that sent a token** means the token expired or was logged out, so it clears the session and goes to the login page.
- **Why only when a token was sent?** A wrong password on the login form is also a 401, and that one must show an error, not redirect.
- **`window.location.assign`** fully reloads the page, which also clears every cached piece of data from the old session.

## 3.4 Error messages
Create `frontend/src/api/errors.ts`:
```ts
import axios from "axios"

// FastAPI errors look like {"detail": "Shipment not found"}, and 422 errors like
// {"detail": [{"loc": ["body", "weight"], "msg": "Input should be ..."}]}
export function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    if (!error.response) {
      return "Can't reach the server, is the API running?"
    }

    const detail = error.response.data?.detail
    if (typeof detail === "string") {
      return detail
    }
    if (Array.isArray(detail) && detail.length > 0) {
      const { loc, msg } = detail[0]
      return `${loc.at(-1)}: ${msg}`
    }
  }
  return "Something went wrong"
}
```
Your FastAPI errors always have `detail`, either a string or a 422 list. That central error handling you built on the backend makes this function short.

## 3.5 The React Query client
Create `frontend/src/api/query-client.ts`:
```ts
import { MutationCache, QueryCache, QueryClient } from "@tanstack/react-query"
import axios from "axios"
import { toast } from "sonner"

import { getErrorMessage } from "@/api/errors"

export const queryClient = new QueryClient({
  // Every failed request shows a toast, so pages don't repeat this code.
  // A query can turn it off with meta: { showErrorToast: false }
  queryCache: new QueryCache({
    onError: (error, query) => {
      if (query.meta?.showErrorToast !== false) {
        toast.error(getErrorMessage(error))
      }
    },
  }),
  mutationCache: new MutationCache({
    onError: (error) => toast.error(getErrorMessage(error)),
  }),
  defaultOptions: {
    queries: {
      // Data younger than 30 seconds is shown without asking the API again
      staleTime: 30_000,
      // Try again after network or server errors, but not after 4xx errors:
      // asking again for a missing shipment gives the same answer
      retry: (failureCount, error) => {
        const status = axios.isAxiosError(error) ? error.response?.status : undefined
        return failureCount < 2 && (status === undefined || status >= 500)
      },
    },
  },
})
```
- **Global error toasts.** Every failed request shows a toast, so pages don't repeat error code.
- **`staleTime`** is how long data counts as fresh. Fresh data is shown without asking the API again. Old data is still shown immediately, then refreshed in the background.
- **`retry`** tries again after network or server errors (5xx), but not after 4xx. Asking again for a missing shipment would give the same answer.

## 3.6 Queries and mutations
Create `frontend/src/api/queries.ts`:
```ts
import {
  skipToken,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query"
import { toast } from "sonner"

import { api } from "@/api/client"
import type {
  DeliveryPartnerRead,
  DeliveryPartnerUpdate,
  SellerRead,
  ShipmentCreate,
  ShipmentRead,
  ShipmentUpdate,
  TagName,
} from "@/api/generated"
import type { Role } from "@/auth/session"

// React Query saves each answer under a key. Invalidating a key refetches it,
// and ["shipments"] also matches every key that starts with it
export const queryKeys = {
  profile: (role: Role) => ["profile", role] as const,
  myShipments: (role: Role) => ["shipments", role] as const,
  tagShipments: (tag: TagName | null) => ["shipments", "seller", "tag", tag] as const,
  shipment: (id: string) => ["shipment", id] as const,
  tags: ["tags"] as const,
}

// Queries: read data

// Sellers and partners have different fields, but both have a name and an email
export function useProfile(role: Role) {
  return useQuery<SellerRead | DeliveryPartnerRead>({
    queryKey: queryKeys.profile(role),
    queryFn: () =>
      role === "seller" ? api.seller.getSellerProfile() : api.partner.getPartnerProfile(),
  })
}

export function usePartnerProfile() {
  return useQuery({
    queryKey: queryKeys.profile("partner"),
    queryFn: () => api.partner.getPartnerProfile(),
  })
}

export function useMyShipments(role: Role) {
  return useQuery({
    queryKey: queryKeys.myShipments(role),
    queryFn: () =>
      role === "seller"
        ? api.seller.getSellerShipments()
        : api.partner.getPartnerShipments(),
  })
}

export function useTagShipments(tag: TagName | null) {
  return useQuery({
    queryKey: queryKeys.tagShipments(tag),
    // skipToken: don't run until a tag is chosen
    queryFn: tag ? () => api.tag.getShipmentsByTag({ tag_name: tag }) : skipToken,
  })
}

export function useShipment(id: string, showErrorToast = true) {
  return useQuery({
    queryKey: queryKeys.shipment(id),
    queryFn: () => api.shipment.getShipment({ id }),
    meta: { showErrorToast },
  })
}

export function useTags() {
  return useQuery({
    queryKey: queryKeys.tags,
    queryFn: () => api.tag.getTags(),
    // The tags are fixed, no need to ask again
    staleTime: Infinity,
  })
}

// Mutations: change data

// After a change: show the new shipment right away and refresh the lists
function useShipmentChanged() {
  const queryClient = useQueryClient()

  return (shipment: ShipmentRead) => {
    queryClient.setQueryData(queryKeys.shipment(shipment.id), shipment)
    queryClient.invalidateQueries({ queryKey: ["shipments"] })
  }
}

export function useCreateShipment() {
  const onChanged = useShipmentChanged()

  return useMutation({
    mutationFn: (data: ShipmentCreate) => api.shipment.submitShipment(data),
    onSuccess: (shipment) => {
      onChanged(shipment)
      toast.success("Shipment created, the client got an email")
    },
  })
}

export function useUpdateShipment(id: string) {
  const onChanged = useShipmentChanged()

  return useMutation({
    mutationFn: (data: ShipmentUpdate) => api.shipment.updateShipment({ id }, data),
    onSuccess: (shipment) => {
      onChanged(shipment)
      toast.success("Shipment updated")
    },
  })
}

export function useVerifyDelivery(id: string) {
  const onChanged = useShipmentChanged()

  return useMutation({
    mutationFn: (code: string) => api.shipment.verifyDelivery({ id }, { code }),
    onSuccess: (shipment) => {
      onChanged(shipment)
      toast.success("Delivered!")
    },
  })
}

export function useResendCode(id: string) {
  return useMutation({
    mutationFn: () => api.shipment.resendVerificationCode({ id }),
    onSuccess: (message) => toast.success(message.detail),
  })
}

export function useCancelShipment(id: string) {
  const onChanged = useShipmentChanged()

  return useMutation({
    mutationFn: () => api.shipment.cancelShipment({ id }),
    onSuccess: (shipment) => {
      onChanged(shipment)
      toast.success("Shipment cancelled")
    },
  })
}

export function useAddTag(id: string) {
  const onChanged = useShipmentChanged()

  return useMutation({
    mutationFn: (tag: TagName) => api.shipment.addTag({ id, tag_name: tag }),
    onSuccess: onChanged,
  })
}

export function useRemoveTag(id: string) {
  const onChanged = useShipmentChanged()

  return useMutation({
    mutationFn: (tag: TagName) => api.shipment.removeTag({ id, tag_name: tag }),
    onSuccess: onChanged,
  })
}

export function useUpdatePartner() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: DeliveryPartnerUpdate) => api.partner.updateDeliveryPartner(data),
    onSuccess: (partner) => {
      queryClient.setQueryData(queryKeys.profile("partner"), partner)
      toast.success("Profile saved")
    },
  })
}
```
**React Query in 5 ideas:**
1. **`useQuery` reads data.** It returns `{ data, isPending, isError }`, and React redraws the page when they change.
2. **`queryKey` names the data in the cache**, like `["shipment", id]`. Two components with the same key share one request and one cached answer.
3. **`useMutation` changes data** (POST, PATCH, DELETE). You call `mutation.mutate(values)` and get `isPending`, `onSuccess` and `onError`.
4. **After a change, update the cache.** `setQueryData` puts the new shipment in right away. `invalidateQueries({ queryKey: ["shipments"] })` marks every list starting with `"shipments"` as old, so they refetch. That's why the dashboard is already correct when you go back to it.
5. **`skipToken`** means "don't run this query yet". The tag filter only fetches once a tag is chosen.

**Why the hooks live in one file:** pages never call `api` directly for reading. They call `useShipment(id)`. Keys, caching and toasts live in one place, so it's easy to change and to test.

---

# Part 4: Auth with React Context

**What is Context?** Normally data travels down through props, from parent to child to grandchild. Context lets any component, however deep, read a value from a "provider" above it. We use it for the session, because the sidebar, the forms and the route guard all need it.

Create `frontend/src/auth/auth-context.ts`:
```ts
import { createContext, useContext } from "react"

import type { Role, Session } from "@/auth/session"

export interface AuthContextValue {
  session: Session | null
  login: (role: Role, email: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

export const AuthContext = createContext<AuthContextValue | null>(null)

// Any component can call useAuth() to read the session or log in and out
export function useAuth() {
  const auth = useContext(AuthContext)
  if (!auth) {
    throw new Error("useAuth must be used inside <AuthProvider>")
  }
  return auth
}

// For pages behind <RequireAuth>, where someone is always logged in
export function useRole(): Role {
  const { session } = useAuth()
  if (!session) {
    throw new Error("useRole must be used on a page behind <RequireAuth>")
  }
  return session.role
}
```
Create `frontend/src/auth/auth-provider.tsx`:
```tsx
import { useQueryClient } from "@tanstack/react-query"
import { useState, type ReactNode } from "react"

import { api } from "@/api/client"
import { AuthContext } from "@/auth/auth-context"
import {
  clearSession,
  getSession,
  saveSession,
  type Role,
  type Session,
} from "@/auth/session"

export function AuthProvider({ children }: { children: ReactNode }) {
  // Starts from localStorage, so a page refresh keeps you logged in
  const [session, setSession] = useState<Session | null>(getSession)
  const queryClient = useQueryClient()

  async function login(role: Role, email: string, password: string) {
    // OAuth2 login forms call the email "username"
    const form = { username: email, password }
    const token =
      role === "seller"
        ? await api.seller.loginSeller(form)
        : await api.partner.loginDeliveryPartner(form)

    const newSession = { token: token.access_token, role }
    saveSession(newSession)
    setSession(newSession)
  }

  async function logout() {
    try {
      // The API puts the token on its Redis blacklist, so it can't be used again
      if (session?.role === "partner") {
        await api.partner.logoutDeliveryPartner()
      } else {
        await api.seller.logoutSeller()
      }
    } finally {
      clearSession()
      setSession(null)
      // Forget the cached data of the user who logged out
      queryClient.clear()
    }
  }

  return <AuthContext value={{ session, login, logout }}>{children}</AuthContext>
}
```
Create `frontend/src/auth/require-auth.tsx`:
```tsx
import { Navigate, Outlet, useLocation } from "react-router"

import { useAuth } from "@/auth/auth-context"
import type { Role } from "@/auth/session"

// Wraps the pages of one role. This only improves the experience: the real
// protection is the API, which checks the token on every request
export function RequireAuth({ role }: { role: Role }) {
  const { session } = useAuth()
  const location = useLocation()

  if (!session) {
    // Remember the page, the login form comes back to it
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  if (session.role !== role) {
    return <Navigate to={`/${session.role}`} replace />
  }
  // <Outlet /> shows the child route that matched the URL
  return <Outlet />
}
```
- **Why two files, `auth-context.ts` and `auth-provider.tsx`?** Vite's fast refresh, which updates the page while you edit, only works when a `.tsx` file exports components only. The `useAuth` hook therefore lives in a separate file. The linter warns about this rule (`only-export-components`).
- **`<AuthContext value={...}>`** is React 19's shorter way to write `<AuthContext.Provider value={...}>`.
- **`useState(getSession)`** passes the function itself, not `getSession()`. React then reads localStorage only once, on the first render.
- **Remember:** `RequireAuth` only improves the experience. **Security is the backend's job**, and it already checks the token and the ownership on every request, like the `cancel` fix.

---

# Part 5: Small shared pieces

Create `frontend/src/lib/format.ts`:
```ts
import type { ShipmentStatus } from "@/api/generated"

export const STATUS_LABELS: Record<ShipmentStatus, string> = {
  placed: "Placed",
  in_transit: "In transit",
  out_for_delivery: "Out for delivery",
  delivered: "Delivered",
  cancelled: "Cancelled",
}

// Same rule as the API: nothing can change after these
export function isFinished(status: ShipmentStatus | null) {
  return status === "delivered" || status === "cancelled"
}

export function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value))
}

// "temperature_controlled" -> "Temperature controlled"
export function formatTagName(name: string) {
  const words = name.replaceAll("_", " ")
  return words.charAt(0).toUpperCase() + words.slice(1)
}

// Zip codes typed as "11001, 11002"
export const ZIP_CODE_LIST = /^\s*\d+(\s*,\s*\d+)*\s*$/

export function parseZipCodes(text: string): number[] {
  return text.split(",").map((zipCode) => Number(zipCode.trim()))
}
```
`Intl.DateTimeFormat` is built into every browser. It shows dates in the user's own format and language, so we don't need a date library.

There's one backend quirk here. Timeline `created_at` values have **no timezone**, because the model uses `datetime.now()`. `estimated_delivery` has one (`...Z`). Browsers read a date without a timezone as local time, which is correct while the server and the browser are in the same timezone. A later backend fix would be `datetime.now(UTC)` with a timezone-aware column.

Create `frontend/src/components/form-field.tsx`:
```tsx
import type { ReactNode } from "react"

import { Field, FieldDescription, FieldError, FieldLabel } from "@/components/ui/field"

// A label, the input passed as children, an optional hint and the error under it
export function FormField({
  id,
  label,
  error,
  description,
  children,
}: {
  id: string
  label: string
  error?: { message?: string }
  description?: string
  children: ReactNode
}) {
  return (
    <Field data-invalid={!!error}>
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      {children}
      {description && <FieldDescription>{description}</FieldDescription>}
      <FieldError errors={[error]} />
    </Field>
  )
}
```
This wraps shadcn's `Field` parts (label, input, hint, error), so every form field takes 3 lines instead of 8. A tiny component that removes repetition is a very common React pattern.

Create `frontend/src/components/logo.tsx`:
```tsx
import { TruckIcon } from "lucide-react"
import { Link } from "react-router"

export function Logo() {
  return (
    <Link to="/" className="flex items-center gap-2 font-medium">
      <div className="flex size-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
        <TruckIcon className="size-4" />
      </div>
      FastShip
    </Link>
  )
}
```
`<Link>` from React Router changes the URL **without reloading the page**. A normal `<a href>` would restart the whole app.

Create `frontend/src/components/page-header.tsx`:
```tsx
import type { ReactNode } from "react"

export function PageHeader({
  title,
  description,
  children,
}: {
  title: string
  description?: string
  // Buttons shown on the right
  children?: ReactNode
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="text-muted-foreground">{description}</p>}
      </div>
      {children && <div className="flex flex-wrap gap-2">{children}</div>}
    </div>
  )
}
```
Create `frontend/src/components/stat-card.tsx`:
```tsx
import type { ReactNode } from "react"

import {
  Card,
  CardAction,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"

export function StatCard({
  title,
  value,
  icon,
}: {
  title: string
  value: ReactNode
  icon: ReactNode
}) {
  return (
    <Card>
      <CardHeader>
        <CardDescription>{title}</CardDescription>
        <CardTitle className="text-3xl tabular-nums">{value}</CardTitle>
        <CardAction className="text-muted-foreground">{icon}</CardAction>
      </CardHeader>
    </Card>
  )
}
```
Create `frontend/src/components/status-badge.tsx`:
```tsx
import type { ShipmentStatus } from "@/api/generated"
import { Badge } from "@/components/ui/badge"
import { STATUS_LABELS } from "@/lib/format"

const COLORS: Record<ShipmentStatus, string> = {
  placed: "bg-slate-100 text-slate-700",
  in_transit: "bg-blue-100 text-blue-700",
  out_for_delivery: "bg-amber-100 text-amber-800",
  delivered: "bg-green-100 text-green-700",
  cancelled: "bg-red-100 text-red-700",
}

export function StatusBadge({ status }: { status: ShipmentStatus | null }) {
  if (!status) {
    return <Badge variant="outline">Unknown</Badge>
  }
  return <Badge className={COLORS[status]}>{STATUS_LABELS[status]}</Badge>
}
```
`Record<ShipmentStatus, string>` means TypeScript **makes you list every status**. If the backend adds a status and you regenerate the client, this file stops building until you add a color for it.

Create `frontend/src/components/shipment-details.tsx`:
```tsx
import type { ShipmentRead } from "@/api/generated"
import { StatusBadge } from "@/components/status-badge"
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { formatDate, formatTagName } from "@/lib/format"

export function ShipmentDetails({
  shipment,
  showTags = true,
}: {
  shipment: ShipmentRead
  showTags?: boolean
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-xl">{shipment.content}</CardTitle>
        <CardDescription className="font-mono text-xs break-all">
          {shipment.id}
        </CardDescription>
        <CardAction>
          <StatusBadge status={shipment.status} />
        </CardAction>
      </CardHeader>
      <CardContent className="flex flex-col gap-6">
        <dl className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-3">
          <Detail label="Weight" value={`${shipment.weight} kg`} />
          <Detail label="Destination" value={`Zip code ${shipment.destination}`} />
          <Detail
            label="Estimated delivery"
            value={formatDate(shipment.estimated_delivery)}
          />
        </dl>

        {showTags && shipment.tags.length > 0 && (
          <div className="flex flex-col gap-2">
            <h3 className="text-sm font-medium">Handling instructions</h3>
            <ul className="flex flex-col gap-1 text-sm">
              {shipment.tags.map((tag) => (
                <li key={tag.name}>
                  <span className="font-medium">{formatTagName(tag.name)}:</span>{" "}
                  {tag.instruction}
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-medium">{value}</dd>
    </div>
  )
}
```
Create `frontend/src/components/shipment-timeline.tsx`:
```tsx
import type { ShipmentEvent } from "@/api/generated"
import { StatusBadge } from "@/components/status-badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { formatDate } from "@/lib/format"

export function ShipmentTimeline({ events }: { events: ShipmentEvent[] }) {
  // The API sends the oldest event first, the newest goes on top here.
  // A copy, because reverse() changes the array it's called on
  const newestFirst = [...events].reverse()

  return (
    <Card>
      <CardHeader>
        <CardTitle>Timeline</CardTitle>
      </CardHeader>
      <CardContent>
        <ol className="flex flex-col gap-6 border-l pl-6">
          {newestFirst.map((event) => (
            <li key={event.id} className="relative">
              <span className="absolute top-1.5 -left-[30.5px] size-3 rounded-full bg-primary ring-4 ring-card" />
              <div className="flex flex-wrap items-center gap-2">
                <StatusBadge status={event.status} />
                <span className="text-sm text-muted-foreground">
                  {formatDate(event.created_at)}
                </span>
              </div>
              <p className="mt-1 text-sm">{event.description}</p>
              <p className="text-xs text-muted-foreground">Zip code {event.location}</p>
            </li>
          ))}
        </ol>
      </CardContent>
    </Card>
  )
}
```
Create `frontend/src/components/shipments-table.tsx`:
```tsx
import { Link } from "react-router"

import type { ShipmentRead } from "@/api/generated"
import { StatusBadge } from "@/components/status-badge"
import { Badge } from "@/components/ui/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { formatDate, formatTagName } from "@/lib/format"

export function ShipmentsTable({
  shipments,
  basePath,
}: {
  shipments: ShipmentRead[]
  // Each row links to `${basePath}/${shipment.id}`
  basePath: string
}) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Content</TableHead>
          <TableHead>Status</TableHead>
          {/* Hidden on small screens, so the table fits on a phone */}
          <TableHead className="hidden md:table-cell">Destination</TableHead>
          <TableHead className="hidden lg:table-cell">Tags</TableHead>
          <TableHead className="hidden sm:table-cell">Estimated delivery</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {shipments.map((shipment) => (
          <TableRow key={shipment.id}>
            <TableCell className="font-medium">
              <Link to={`${basePath}/${shipment.id}`} className="hover:underline">
                {shipment.content}
              </Link>
            </TableCell>
            <TableCell>
              <StatusBadge status={shipment.status} />
            </TableCell>
            <TableCell className="hidden md:table-cell">{shipment.destination}</TableCell>
            <TableCell className="hidden lg:table-cell">
              <div className="flex flex-wrap gap-1">
                {shipment.tags.map((tag) => (
                  <Badge key={tag.name} variant="outline">
                    {formatTagName(tag.name)}
                  </Badge>
                ))}
              </div>
            </TableCell>
            <TableCell className="hidden sm:table-cell">
              {formatDate(shipment.estimated_delivery)}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
```
`hidden md:table-cell` hides a column on small screens and shows it from medium width up. This is how Tailwind handles **responsive design**: classes without a prefix apply to phones first, and `sm:`, `md:`, `lg:` add rules for wider screens.

Create `frontend/src/components/qr-scanner-dialog.tsx`:
```tsx
import {
  Scanner,
  type IDetectedBarcode,
  type IScannerError,
} from "@yudiel/react-qr-scanner"
import { toast } from "sonner"

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

// Clear messages for the camera problems people actually hit
const CAMERA_ERRORS: Partial<Record<IScannerError["kind"], string>> = {
  "permission-denied": "Allow the camera for this site in the browser settings",
  "no-camera": "No camera found on this device",
  "in-use": "Another app is using the camera",
  "insecure-context": "The camera only works on https:// or localhost",
}

export function QrScannerDialog({
  open,
  onOpenChange,
  onCode,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCode: (code: string) => void
}) {
  function handleScan(codes: IDetectedBarcode[]) {
    const value = codes[0]?.rawValue.trim() ?? ""
    if (/^\d{6}$/.test(value)) {
      onCode(value)
    } else {
      toast.error("This QR code isn't a delivery code")
    }
  }

  function handleError(error: IScannerError) {
    toast.error(CAMERA_ERRORS[error.kind] ?? `Camera error: ${error.message || error.kind}`)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Scan the delivery code</DialogTitle>
          <DialogDescription>
            Point the camera at the QR code in the client's email.
          </DialogDescription>
        </DialogHeader>
        {/* The dialog removes its content when closed, which turns the camera off */}
        <div className="overflow-hidden rounded-lg">
          <Scanner
            onScan={handleScan}
            onError={handleError}
            formats={["qr_code"]}
            // The back camera on phones, any camera on a computer. Sizes are only
            // "ideal": the library's default minimum (640x640) fails on many webcams
            constraints={{
              facingMode: "environment",
              width: { ideal: 1280 },
              height: { ideal: 720 },
            }}
            sound={false}
          />
        </div>
      </DialogContent>
    </Dialog>
  )
}
```
**Camera compatibility.** You asked for scanning on both PC and phone, and these are the 3 decisions that make it work:
1. **`facingMode: "environment"`** uses the back camera on phones. On a laptop it falls back to the webcam.
2. **The camera size is only "ideal".** The library's default demands at least 640×640, and many laptop webcams can't do that, so they fail with "overconstrained". My test hit exactly this error.
3. **The decoder:** Chrome and Edge decode QR codes natively (`BarcodeDetector`). On Safari and Firefox, the library downloads a small decoder the first time it's used.

---

# Part 6: Layout and sidebar (adapted from the sidebar-07 block)

Replace the whole of `frontend/src/components/nav-main.tsx`:
```tsx
import type { ReactNode } from "react"
import { Link, useLocation } from "react-router"

import {
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar"

export interface NavItem {
  title: string
  url: string
  icon: ReactNode
}

export function NavMain({ items }: { items: NavItem[] }) {
  const { pathname } = useLocation()
  const { setOpenMobile } = useSidebar()

  return (
    <SidebarGroup>
      <SidebarGroupLabel>Menu</SidebarGroupLabel>
      <SidebarMenu>
        {items.map((item) => (
          <SidebarMenuItem key={item.url}>
            {/* asChild: the button's style goes on the Link, so it's one clickable link */}
            <SidebarMenuButton asChild isActive={pathname === item.url} tooltip={item.title}>
              {/* On phones the sidebar is a drawer, close it after a click */}
              <Link to={item.url} onClick={() => setOpenMobile(false)}>
                {item.icon}
                <span>{item.title}</span>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        ))}
      </SidebarMenu>
    </SidebarGroup>
  )
}
```
Replace the whole of `frontend/src/components/nav-user.tsx`:
```tsx
import { ChevronsUpDownIcon, LogOutIcon } from "lucide-react"
import { useNavigate } from "react-router"

import { useProfile } from "@/api/queries"
import { useAuth, useRole } from "@/auth/auth-context"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar"

export function NavUser() {
  const role = useRole()
  const { logout } = useAuth()
  const { data: user } = useProfile(role)
  const { isMobile } = useSidebar()
  const navigate = useNavigate()

  const name = user?.name ?? ""
  // "Cairo Crafts" -> "CC"
  const initials = name
    .split(" ")
    .map((word) => word[0])
    .join("")
    .slice(0, 2)
    .toUpperCase()

  async function handleLogout() {
    await logout()
    navigate("/login")
  }

  const userInfo = (
    <>
      <Avatar className="h-8 w-8 rounded-lg">
        <AvatarFallback className="rounded-lg">{initials}</AvatarFallback>
      </Avatar>
      <div className="grid flex-1 text-left text-sm leading-tight">
        <span className="truncate font-medium">{name}</span>
        <span className="truncate text-xs">{user?.email}</span>
      </div>
    </>
  )

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton
              size="lg"
              className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
            >
              {userInfo}
              <ChevronsUpDownIcon className="ml-auto size-4" />
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            className="w-(--radix-dropdown-menu-trigger-width) min-w-56"
            side={isMobile ? "bottom" : "right"}
            align="end"
            sideOffset={4}
          >
            <DropdownMenuLabel className="p-0 font-normal">
              <div className="flex items-center gap-2 px-1 py-1.5 text-left text-sm">
                {userInfo}
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={handleLogout}>
              <LogOutIcon />
              Log out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}
```
Replace the whole of `frontend/src/components/app-sidebar.tsx`:
```tsx
import {
  LayoutDashboardIcon,
  PackagePlusIcon,
  TruckIcon,
  UserCogIcon,
} from "lucide-react"
import { Link } from "react-router"

import { useRole } from "@/auth/auth-context"
import type { Role } from "@/auth/session"
import { NavMain, type NavItem } from "@/components/nav-main"
import { NavUser } from "@/components/nav-user"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from "@/components/ui/sidebar"

// The pages each role can open from the sidebar
const NAV_ITEMS: Record<Role, NavItem[]> = {
  seller: [
    { title: "Dashboard", url: "/seller", icon: <LayoutDashboardIcon /> },
    { title: "New shipment", url: "/seller/shipments/new", icon: <PackagePlusIcon /> },
  ],
  partner: [
    { title: "Dashboard", url: "/partner", icon: <LayoutDashboardIcon /> },
    { title: "Profile", url: "/partner/profile", icon: <UserCogIcon /> },
  ],
}

export function AppSidebar(props: React.ComponentProps<typeof Sidebar>) {
  const role = useRole()

  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild>
              <Link to={`/${role}`}>
                <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
                  <TruckIcon className="size-4" />
                </div>
                <div className="grid flex-1 text-left text-sm leading-tight">
                  <span className="truncate font-medium">FastShip</span>
                  <span className="truncate text-xs">
                    {role === "seller" ? "Seller" : "Delivery partner"}
                  </span>
                </div>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <NavMain items={NAV_ITEMS[role]} />
      </SidebarContent>
      <SidebarFooter>
        <NavUser />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
```
Create `frontend/src/layouts/dashboard-layout.tsx`:
```tsx
import { Outlet } from "react-router"

import { useRole } from "@/auth/auth-context"
import { AppSidebar } from "@/components/app-sidebar"
import { Separator } from "@/components/ui/separator"
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"

// The frame around every seller and partner page: sidebar on the left,
// the page itself where <Outlet /> is
export function DashboardLayout() {
  const role = useRole()

  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <header className="flex h-14 shrink-0 items-center gap-2 border-b px-4">
          <SidebarTrigger className="-ml-1" />
          <Separator
            orientation="vertical"
            className="mr-2 data-vertical:h-4 data-vertical:self-auto"
          />
          <span className="text-sm text-muted-foreground">
            {role === "seller" ? "Seller dashboard" : "Partner dashboard"}
          </span>
        </header>
        <main className="flex flex-1 flex-col gap-6 p-4 md:p-6">
          <Outlet />
        </main>
      </SidebarInset>
    </SidebarProvider>
  )
}
```

**What we changed in the block:**
- **Sample data** became each role's real pages (`NAV_ITEMS`).
- **`<a href>`** became `<Link to>`, so there are no page reloads.
- **Collapsible sub-menus** were removed. We only have a few pages.
- **The team switcher** became the FastShip logo.
- **The user menu** shows the real user (from `GET /seller/me` or `/partner/me`) and has a working **Log out**.
- **On phones**, the sidebar becomes a slide-in drawer, and it closes after you pick a page.

**`asChild`** is used all over shadcn. It means "don't render your own `<button>`, put your styles and behavior on my child instead". For example, a sidebar button that *is* a router `<Link>`.

---

# Part 7: Forms (react-hook-form + zod)

**How every form in this app works:**
1. **A zod schema lists the rules,** for example `z.email("Enter a valid email")`.
2. **`z.infer<typeof schema>`** makes the TypeScript type from the schema. The rules and the type can't drift apart.
3. **`useForm({ resolver: zodResolver(schema) })`** connects the schema to the form.
4. **`{...register("email")}`** connects an input to the form. React doesn't redraw on every key press, which makes these forms fast.
5. **`handleSubmit(onSubmit)`** checks the rules first. `onSubmit` only runs with valid values, and wrong fields show their messages.
6. **The backend still validates everything.** Frontend rules exist for quick feedback. Server rules exist for security.

Replace the whole of `frontend/src/components/login-form.tsx`:
```tsx
import { zodResolver } from "@hookform/resolvers/zod"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { Link, useLocation, useNavigate, useSearchParams } from "react-router"
import { z } from "zod"

import { getErrorMessage } from "@/api/errors"
import { useAuth } from "@/auth/auth-context"
import type { Role } from "@/auth/session"
import { FormField } from "@/components/form-field"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Field, FieldDescription, FieldError, FieldGroup } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"

// The rules each field must follow, checked before anything is sent
const loginSchema = z.object({
  email: z.email("Enter a valid email"),
  password: z.string().min(1, "Enter your password"),
})

// The TypeScript type of the form values, made from the schema
type LoginValues = z.infer<typeof loginSchema>

export function LoginForm() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams] = useSearchParams()

  const [role, setRole] = useState<Role>(
    searchParams.get("role") === "partner" ? "partner" : "seller",
  )

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({ resolver: zodResolver(loginSchema) })

  async function onSubmit(values: LoginValues) {
    try {
      await login(role, values.email, values.password)
      // Back to the page that asked for a login, or to the dashboard
      const from = (location.state as { from?: string } | null)?.from
      navigate(from?.startsWith(`/${role}`) ? from : `/${role}`, { replace: true })
    } catch (error) {
      // "root" is for an error about the whole form, not one field
      setError("root", { message: getErrorMessage(error) })
    }
  }

  return (
    <Card>
      <CardHeader className="text-center">
        <CardTitle className="text-xl">Welcome back</CardTitle>
        <CardDescription>
          {searchParams.has("expired")
            ? "Your session expired, please log in again"
            : "Log in to your FastShip account"}
        </CardDescription>
      </CardHeader>
      <CardContent>
        {/* handleSubmit checks the schema first, onSubmit only runs when it's valid */}
        <form onSubmit={handleSubmit(onSubmit)} noValidate>
          <FieldGroup>
            <Tabs value={role} onValueChange={(value) => setRole(value as Role)}>
              <TabsList className="w-full">
                <TabsTrigger value="seller">Seller</TabsTrigger>
                <TabsTrigger value="partner">Delivery partner</TabsTrigger>
              </TabsList>
            </Tabs>
            <FormField id="email" label="Email" error={errors.email}>
              <Input
                id="email"
                type="email"
                placeholder="you@example.com"
                autoComplete="email"
                aria-invalid={!!errors.email}
                {...register("email")}
              />
            </FormField>
            <FormField id="password" label="Password" error={errors.password}>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                aria-invalid={!!errors.password}
                {...register("password")}
              />
            </FormField>
            <Field>
              <FieldError errors={[errors.root]} />
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting && <Spinner />}
                Log in
              </Button>
              <FieldDescription className="text-center">
                Don&apos;t have an account? <Link to="/signup">Sign up</Link>
              </FieldDescription>
            </Field>
          </FieldGroup>
        </form>
      </CardContent>
    </Card>
  )
}
```
Replace the whole of `frontend/src/components/signup-form.tsx`:
```tsx
import { zodResolver } from "@hookform/resolvers/zod"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { Link, useNavigate } from "react-router"
import { toast } from "sonner"
import { z } from "zod"

import { api } from "@/api/client"
import { getErrorMessage } from "@/api/errors"
import { useAuth } from "@/auth/auth-context"
import type { Role } from "@/auth/session"
import { FormField } from "@/components/form-field"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Field, FieldDescription, FieldError, FieldGroup } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { parseZipCodes, ZIP_CODE_LIST } from "@/lib/format"

// Both roles need a name, email and password, then each adds its own fields
const accountSchema = z.object({
  name: z.string().min(1, "Enter your name"),
  email: z.email("Enter a valid email"),
  password: z.string().min(8, "At least 8 characters"),
})

const sellerSchema = accountSchema.extend({
  // valueAsNumber turns an empty input into NaN, this message covers it too
  zip_code: z.number({ error: "Enter a zip code" }).int().positive(),
  address: z.string(),
})

const partnerSchema = accountSchema.extend({
  serviceable_zip_codes: z
    .string()
    .regex(ZIP_CODE_LIST, "Zip codes separated by commas, like 11001, 11002"),
  max_handling_capacity: z.number({ error: "Enter a number" }).int().min(1),
})

type SellerValues = z.infer<typeof sellerSchema>
type PartnerValues = z.infer<typeof partnerSchema>

export function SignupForm() {
  const [role, setRole] = useState<Role>("seller")

  return (
    <Card>
      <CardHeader className="text-center">
        <CardTitle className="text-xl">Create your account</CardTitle>
        <CardDescription>Sellers send shipments, partners deliver them</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-6">
        <Tabs value={role} onValueChange={(value) => setRole(value as Role)}>
          <TabsList className="w-full">
            <TabsTrigger value="seller">Seller</TabsTrigger>
            <TabsTrigger value="partner">Delivery partner</TabsTrigger>
          </TabsList>
        </Tabs>
        {/* Each role has its own form, with its own fields and rules */}
        {role === "seller" ? <SellerSignup /> : <PartnerSignup />}
        <FieldDescription className="text-center">
          Already have an account? <Link to={`/login?role=${role}`}>Log in</Link>
        </FieldDescription>
      </CardContent>
    </Card>
  )
}

// After signing up, log in with the same email and password
function useLoginAfterSignup(role: Role) {
  const { login } = useAuth()
  const navigate = useNavigate()

  return async (email: string, password: string) => {
    await login(role, email, password)
    toast.success("Welcome to FastShip!")
    navigate(`/${role}`, { replace: true })
  }
}

function SellerSignup() {
  const loginAfterSignup = useLoginAfterSignup("seller")
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<SellerValues>({ resolver: zodResolver(sellerSchema) })

  async function onSubmit(values: SellerValues) {
    try {
      await api.seller.registerSeller({ ...values, address: values.address || null })
      await loginAfterSignup(values.email, values.password)
    } catch (error) {
      setError("root", { message: getErrorMessage(error) })
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate>
      <FieldGroup>
        <FormField id="name" label="Business name" error={errors.name}>
          <Input id="name" aria-invalid={!!errors.name} {...register("name")} />
        </FormField>
        <FormField id="email" label="Email" error={errors.email}>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            aria-invalid={!!errors.email}
            {...register("email")}
          />
        </FormField>
        <FormField id="password" label="Password" error={errors.password}>
          <Input
            id="password"
            type="password"
            autoComplete="new-password"
            aria-invalid={!!errors.password}
            {...register("password")}
          />
        </FormField>
        <FormField
          id="zip_code"
          label="Zip code"
          error={errors.zip_code}
          description="Your shipments start from here"
        >
          <Input
            id="zip_code"
            type="number"
            placeholder="11001"
            aria-invalid={!!errors.zip_code}
            {...register("zip_code", { valueAsNumber: true })}
          />
        </FormField>
        <FormField id="address" label="Address (optional)">
          <Input id="address" {...register("address")} />
        </FormField>
        <SubmitButton isSubmitting={isSubmitting} error={errors.root} />
      </FieldGroup>
    </form>
  )
}

function PartnerSignup() {
  const loginAfterSignup = useLoginAfterSignup("partner")
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<PartnerValues>({ resolver: zodResolver(partnerSchema) })

  async function onSubmit(values: PartnerValues) {
    try {
      await api.partner.registerDeliveryPartner({
        ...values,
        serviceable_zip_codes: parseZipCodes(values.serviceable_zip_codes),
      })
      await loginAfterSignup(values.email, values.password)
    } catch (error) {
      setError("root", { message: getErrorMessage(error) })
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate>
      <FieldGroup>
        <FormField id="name" label="Name" error={errors.name}>
          <Input id="name" aria-invalid={!!errors.name} {...register("name")} />
        </FormField>
        <FormField id="email" label="Email" error={errors.email}>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            aria-invalid={!!errors.email}
            {...register("email")}
          />
        </FormField>
        <FormField id="password" label="Password" error={errors.password}>
          <Input
            id="password"
            type="password"
            autoComplete="new-password"
            aria-invalid={!!errors.password}
            {...register("password")}
          />
        </FormField>
        <FormField
          id="serviceable_zip_codes"
          label="Zip codes you deliver to"
          error={errors.serviceable_zip_codes}
        >
          <Input
            id="serviceable_zip_codes"
            placeholder="11001, 11002"
            aria-invalid={!!errors.serviceable_zip_codes}
            {...register("serviceable_zip_codes")}
          />
        </FormField>
        <FormField
          id="max_handling_capacity"
          label="Shipments you can handle at once"
          error={errors.max_handling_capacity}
        >
          <Input
            id="max_handling_capacity"
            type="number"
            placeholder="10"
            aria-invalid={!!errors.max_handling_capacity}
            {...register("max_handling_capacity", { valueAsNumber: true })}
          />
        </FormField>
        <SubmitButton isSubmitting={isSubmitting} error={errors.root} />
      </FieldGroup>
    </form>
  )
}

function SubmitButton({
  isSubmitting,
  error,
}: {
  isSubmitting: boolean
  error?: { message?: string }
}) {
  return (
    <Field>
      <FieldError errors={[error]} />
      <Button type="submit" disabled={isSubmitting}>
        {isSubmitting && <Spinner />}
        Create account
      </Button>
    </Field>
  )
}
```
- **`valueAsNumber: true`** sends numbers, not strings. An empty number input becomes `NaN`, so the zod message "Enter a zip code" covers it.
- **Zip codes are typed as text**, like "11001, 11002", and turned into `[11001, 11002]` only when sending. That keeps the form simple.
- **`setError("root", ...)`** shows an API error for the whole form, like "Email already registered".
- **The password needs 8 characters in the frontend only.** For real security, add the same rule to the backend's `SellerCreate` and `DeliveryPartnerCreate` schemas later.

---

# Part 8: Pages

## Public pages
Create `frontend/src/pages/home-page.tsx`:
```tsx
import { useState, type FormEvent } from "react"
import { Link, useNavigate } from "react-router"

import { useAuth } from "@/auth/auth-context"
import { Logo } from "@/components/logo"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

export function HomePage() {
  const { session } = useAuth()
  const navigate = useNavigate()
  // One input doesn't need a form library, useState is enough
  const [trackingId, setTrackingId] = useState("")

  function handleTrack(event: FormEvent) {
    // Stop the browser from reloading the page, React Router changes the URL instead
    event.preventDefault()
    navigate(`/track/${trackingId.trim()}`)
  }

  return (
    <div className="flex min-h-svh flex-col">
      <header className="flex items-center justify-between p-4 md:px-10">
        <Logo />
        <nav className="flex gap-2">
          {session ? (
            <Button asChild>
              <Link to={`/${session.role}`}>Dashboard</Link>
            </Button>
          ) : (
            <>
              <Button variant="ghost" asChild>
                <Link to="/login">Log in</Link>
              </Button>
              <Button asChild>
                <Link to="/signup">Sign up</Link>
              </Button>
            </>
          )}
        </nav>
      </header>

      <main className="flex flex-1 flex-col items-center justify-center gap-8 p-6 text-center">
        <div className="flex max-w-2xl flex-col gap-4">
          <h1 className="text-4xl font-semibold tracking-tight md:text-5xl">
            Ship it fast, track it live
          </h1>
          <p className="text-lg text-muted-foreground">
            Sellers create shipments, delivery partners bring them to the door, and
            clients follow every step.
          </p>
        </div>
        <form onSubmit={handleTrack} className="flex w-full max-w-md gap-2">
          <Input
            aria-label="Tracking id"
            placeholder="Paste your tracking id"
            value={trackingId}
            onChange={(event) => setTrackingId(event.target.value)}
          />
          <Button type="submit" disabled={!trackingId.trim()}>
            Track
          </Button>
        </form>
      </main>
    </div>
  )
}
```
This page shows the **simplest form technique**: `useState` plus `onChange`. One input doesn't need a form library.

Create `frontend/src/pages/login-page.tsx`:
```tsx
import { Navigate } from "react-router"

import { useAuth } from "@/auth/auth-context"
import { LoginForm } from "@/components/login-form"
import { Logo } from "@/components/logo"

export function LoginPage() {
  const { session } = useAuth()

  // Already logged in: nothing to do here
  if (session) {
    return <Navigate to={`/${session.role}`} replace />
  }

  return (
    <div className="flex min-h-svh flex-col items-center justify-center gap-6 bg-muted p-6 md:p-10">
      <div className="flex w-full max-w-sm flex-col gap-6">
        <div className="self-center">
          <Logo />
        </div>
        <LoginForm />
      </div>
    </div>
  )
}
```
Create `frontend/src/pages/signup-page.tsx`:
```tsx
import { Navigate } from "react-router"

import { useAuth } from "@/auth/auth-context"
import { Logo } from "@/components/logo"
import { SignupForm } from "@/components/signup-form"

export function SignupPage() {
  const { session } = useAuth()

  if (session) {
    return <Navigate to={`/${session.role}`} replace />
  }

  return (
    <div className="flex min-h-svh flex-col items-center justify-center gap-6 bg-muted p-6 md:p-10">
      <div className="flex w-full max-w-sm flex-col gap-6">
        <div className="self-center">
          <Logo />
        </div>
        <SignupForm />
      </div>
    </div>
  )
}
```
Create `frontend/src/pages/track-page.tsx`:
```tsx
import { PackageSearchIcon } from "lucide-react"
import { Link, useParams } from "react-router"

import { useShipment } from "@/api/queries"
import { Logo } from "@/components/logo"
import { ShipmentDetails } from "@/components/shipment-details"
import { ShipmentTimeline } from "@/components/shipment-timeline"
import { Button } from "@/components/ui/button"
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import { Skeleton } from "@/components/ui/skeleton"

// Public page: the client opens it from the tracking link, no login needed
export function TrackPage() {
  // The :id part of the URL /track/:id
  const { id = "" } = useParams()
  // This page shows its own message instead of a toast
  const { data: shipment, isPending, isError } = useShipment(id, false)

  return (
    <div className="flex min-h-svh flex-col bg-muted">
      <header className="p-4 md:px-10">
        <Logo />
      </header>
      <main className="mx-auto flex w-full max-w-3xl flex-col gap-6 p-4 md:p-6">
        {isPending && <Skeleton className="h-64 w-full" />}

        {isError && (
          <Empty className="bg-background">
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <PackageSearchIcon />
              </EmptyMedia>
              <EmptyTitle>Shipment not found</EmptyTitle>
              <EmptyDescription>Check the tracking id and try again.</EmptyDescription>
            </EmptyHeader>
            <EmptyContent>
              <Button variant="outline" asChild>
                <Link to="/">Back home</Link>
              </Button>
            </EmptyContent>
          </Empty>
        )}

        {shipment && (
          <>
            <ShipmentDetails shipment={shipment} />
            <ShipmentTimeline events={shipment.timeline} />
          </>
        )}
      </main>
    </div>
  )
}
```
Create `frontend/src/pages/not-found-page.tsx`:
```tsx
import { Link } from "react-router"

import { Button } from "@/components/ui/button"
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
} from "@/components/ui/empty"

export function NotFoundPage() {
  return (
    <div className="flex min-h-svh items-center justify-center p-6">
      <Empty>
        <EmptyHeader>
          <EmptyTitle>Page not found</EmptyTitle>
          <EmptyDescription>There's nothing at this address.</EmptyDescription>
        </EmptyHeader>
        <EmptyContent>
          <Button asChild>
            <Link to="/">Back home</Link>
          </Button>
        </EmptyContent>
      </Empty>
    </div>
  )
}
```

**Every page that loads data handles 3 states:** loading (`isPending` shows a skeleton), error (`isError` shows a message), and data. Forgetting the first two is the most common beginner mistake.

## Seller pages
Create `frontend/src/pages/seller/dashboard-page.tsx`:
```tsx
import {
  CircleCheckIcon,
  CircleXIcon,
  PackageIcon,
  PackagePlusIcon,
  TruckIcon,
} from "lucide-react"
import { useState } from "react"
import { Link } from "react-router"

import type { ShipmentRead, TagName } from "@/api/generated"
import { useMyShipments, useTags, useTagShipments } from "@/api/queries"
import { PageHeader } from "@/components/page-header"
import { ShipmentsTable } from "@/components/shipments-table"
import { StatCard } from "@/components/stat-card"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { formatTagName, isFinished } from "@/lib/format"

const FILTERS = {
  all: () => true,
  active: (shipment: ShipmentRead) => !isFinished(shipment.status),
  delivered: (shipment: ShipmentRead) => shipment.status === "delivered",
  cancelled: (shipment: ShipmentRead) => shipment.status === "cancelled",
}
type Filter = keyof typeof FILTERS

export function SellerDashboardPage() {
  const [filter, setFilter] = useState<Filter>("all")
  const [tag, setTag] = useState<TagName | null>(null)

  const shipments = useMyShipments("seller")
  const tagShipments = useTagShipments(tag)
  const tags = useTags()

  const all = shipments.data ?? []
  // With a tag chosen, the list comes from GET /tag/shipments instead
  const list = tag ? tagShipments : shipments
  const visible = (list.data ?? []).filter(FILTERS[filter])

  return (
    <>
      <PageHeader title="Shipments" description="Everything you've sent with FastShip">
        <Button asChild>
          <Link to="/seller/shipments/new">
            <PackagePlusIcon />
            New shipment
          </Link>
        </Button>
      </PageHeader>

      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <StatCard title="Total" value={all.length} icon={<PackageIcon />} />
        <StatCard
          title="Active"
          value={all.filter(FILTERS.active).length}
          icon={<TruckIcon />}
        />
        <StatCard
          title="Delivered"
          value={all.filter(FILTERS.delivered).length}
          icon={<CircleCheckIcon />}
        />
        <StatCard
          title="Cancelled"
          value={all.filter(FILTERS.cancelled).length}
          icon={<CircleXIcon />}
        />
      </div>

      <Card>
        <CardHeader className="flex flex-wrap items-center justify-between gap-4">
          <Tabs value={filter} onValueChange={(value) => setFilter(value as Filter)}>
            <TabsList>
              <TabsTrigger value="all">All</TabsTrigger>
              <TabsTrigger value="active">Active</TabsTrigger>
              <TabsTrigger value="delivered">Delivered</TabsTrigger>
              <TabsTrigger value="cancelled">Cancelled</TabsTrigger>
            </TabsList>
          </Tabs>
          <Select
            value={tag ?? "any"}
            onValueChange={(value) => setTag(value === "any" ? null : (value as TagName))}
          >
            <SelectTrigger className="w-48" aria-label="Filter by tag">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="any">Any tag</SelectItem>
              {tags.data?.map((tag) => (
                <SelectItem key={tag.name} value={tag.name}>
                  {formatTagName(tag.name)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </CardHeader>
        <CardContent>
          {list.isPending ? (
            <div className="flex flex-col gap-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : visible.length === 0 ? (
            <Empty>
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <PackageIcon />
                </EmptyMedia>
                <EmptyTitle>No shipments here</EmptyTitle>
                <EmptyDescription>
                  {all.length === 0
                    ? "Create your first shipment to see it here."
                    : "No shipment matches these filters."}
                </EmptyDescription>
              </EmptyHeader>
            </Empty>
          ) : (
            <ShipmentsTable shipments={visible} basePath="/seller/shipments" />
          )}
        </CardContent>
      </Card>
    </>
  )
}
```
**Derived data:** the stats and the filtered list are **computed during render** from the shipments, not stored in extra `useState`s. This is a key React rule: don't store what you can compute. If you store it, the two copies can disagree.

Create `frontend/src/pages/seller/new-shipment-page.tsx`:
```tsx
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { useNavigate } from "react-router"
import { z } from "zod"

import { useCreateShipment } from "@/api/queries"
import { FormField } from "@/components/form-field"
import { PageHeader } from "@/components/page-header"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { FieldGroup } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"

// The same rules as ShipmentCreate in the API, so mistakes show before sending
const shipmentSchema = z.object({
  content: z.string().min(1, "What's inside the package?"),
  weight: z.number({ error: "Enter the weight" }).gt(0).max(25, "At most 25 kg"),
  destination: z.number({ error: "Enter a zip code" }).int().positive(),
  client_contact_email: z.email("Enter the client's email"),
  // Empty, or a number like +201012345678
  client_contact_phone: z
    .string()
    .regex(/^(\+[1-9]\d{7,14})?$/, "International format, like +201012345678"),
})

type ShipmentValues = z.infer<typeof shipmentSchema>

export function NewShipmentPage() {
  const navigate = useNavigate()
  const createShipment = useCreateShipment()
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ShipmentValues>({ resolver: zodResolver(shipmentSchema) })

  function onSubmit(values: ShipmentValues) {
    createShipment.mutate(
      { ...values, client_contact_phone: values.client_contact_phone || null },
      // Errors, like no partner for this zip code, show as a toast (query-client.ts)
      { onSuccess: (shipment) => navigate(`/seller/shipments/${shipment.id}`) },
    )
  }

  return (
    <>
      <PageHeader
        title="New shipment"
        description="A delivery partner who serves the destination is assigned automatically"
      />
      <Card className="max-w-2xl">
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} noValidate>
            <FieldGroup>
              <FormField id="content" label="Content" error={errors.content}>
                <Input
                  id="content"
                  placeholder="Glass vase"
                  aria-invalid={!!errors.content}
                  {...register("content")}
                />
              </FormField>
              <div className="grid gap-4 sm:grid-cols-2">
                <FormField id="weight" label="Weight (kg)" error={errors.weight}>
                  <Input
                    id="weight"
                    type="number"
                    step="0.1"
                    placeholder="2.5"
                    aria-invalid={!!errors.weight}
                    {...register("weight", { valueAsNumber: true })}
                  />
                </FormField>
                <FormField
                  id="destination"
                  label="Destination zip code"
                  error={errors.destination}
                >
                  <Input
                    id="destination"
                    type="number"
                    placeholder="11001"
                    aria-invalid={!!errors.destination}
                    {...register("destination", { valueAsNumber: true })}
                  />
                </FormField>
              </div>
              <FormField
                id="client_contact_email"
                label="Client email"
                error={errors.client_contact_email}
                description="Gets the tracking link and the delivery code"
              >
                <Input
                  id="client_contact_email"
                  type="email"
                  placeholder="client@example.com"
                  aria-invalid={!!errors.client_contact_email}
                  {...register("client_contact_email")}
                />
              </FormField>
              <FormField
                id="client_contact_phone"
                label="Client phone (optional)"
                error={errors.client_contact_phone}
                description="If set, the delivery code goes by SMS instead"
              >
                <Input
                  id="client_contact_phone"
                  type="tel"
                  placeholder="+201012345678"
                  aria-invalid={!!errors.client_contact_phone}
                  {...register("client_contact_phone")}
                />
              </FormField>
              <Button type="submit" className="self-start" disabled={createShipment.isPending}>
                {createShipment.isPending && <Spinner />}
                Create shipment
              </Button>
            </FieldGroup>
          </form>
        </CardContent>
      </Card>
    </>
  )
}
```
Create `frontend/src/pages/seller/shipment-page.tsx`:
```tsx
import { CopyIcon, XIcon } from "lucide-react"
import { useState } from "react"
import { useParams } from "react-router"
import { toast } from "sonner"

import type { ShipmentRead, TagName } from "@/api/generated"
import {
  useAddTag,
  useCancelShipment,
  useRemoveTag,
  useShipment,
  useTags,
} from "@/api/queries"
import { PageHeader } from "@/components/page-header"
import { ShipmentDetails } from "@/components/shipment-details"
import { ShipmentTimeline } from "@/components/shipment-timeline"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { formatTagName, isFinished } from "@/lib/format"

export function SellerShipmentPage() {
  const { id = "" } = useParams()
  const { data: shipment, isPending, isError } = useShipment(id)

  if (isPending) {
    return <Skeleton className="h-96 w-full" />
  }
  if (isError) {
    return <p className="text-muted-foreground">This shipment couldn't be loaded.</p>
  }

  function copyTrackingLink() {
    // The client's public page, the same one the home page opens
    navigator.clipboard.writeText(`${window.location.origin}/track/${id}`)
    toast.success("Tracking link copied")
  }

  return (
    <>
      <PageHeader title="Shipment" description="Details, tags and the delivery timeline">
        <Button variant="outline" onClick={copyTrackingLink}>
          <CopyIcon />
          Copy tracking link
        </Button>
        <CancelButton shipment={shipment} />
      </PageHeader>
      <div className="grid gap-6 lg:grid-cols-[3fr_2fr]">
        <div className="flex flex-col gap-6">
          <ShipmentDetails shipment={shipment} showTags={false} />
          <TagsCard shipment={shipment} />
        </div>
        <ShipmentTimeline events={shipment.timeline} />
      </div>
    </>
  )
}

function CancelButton({ shipment }: { shipment: ShipmentRead }) {
  const cancel = useCancelShipment(shipment.id)

  return (
    // Asks "are you sure?" first, because cancelling can't be undone
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button variant="destructive" disabled={isFinished(shipment.status)}>
          Cancel shipment
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Cancel this shipment?</AlertDialogTitle>
          <AlertDialogDescription>
            The client gets an email, and the shipment can't be changed after this.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Keep it</AlertDialogCancel>
          <AlertDialogAction variant="destructive" onClick={() => cancel.mutate()}>
            Cancel shipment
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

function TagsCard({ shipment }: { shipment: ShipmentRead }) {
  const [selected, setSelected] = useState<TagName | "">("")
  const tags = useTags()
  const addTag = useAddTag(shipment.id)
  const removeTag = useRemoveTag(shipment.id)

  const locked = isFinished(shipment.status)
  const current = shipment.tags.map((tag) => tag.name)
  const available = (tags.data ?? []).filter((tag) => !current.includes(tag.name))

  return (
    <Card>
      <CardHeader>
        <CardTitle>Tags</CardTitle>
        <CardDescription>Tell the delivery partner how to handle the package</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-wrap gap-2">
          {shipment.tags.length === 0 && (
            <span className="text-sm text-muted-foreground">No tags yet</span>
          )}
          {shipment.tags.map((tag) => (
            <Badge key={tag.name} variant="secondary" title={tag.instruction}>
              {formatTagName(tag.name)}
              {!locked && (
                <button
                  type="button"
                  aria-label={`Remove ${formatTagName(tag.name)}`}
                  className="ml-1 rounded-full hover:text-destructive"
                  onClick={() => removeTag.mutate(tag.name)}
                >
                  <XIcon className="size-3" />
                </button>
              )}
            </Badge>
          ))}
        </div>
        {!locked && (
          <div className="flex gap-2">
            <Select value={selected} onValueChange={(value) => setSelected(value as TagName)}>
              <SelectTrigger className="w-56" aria-label="Tag to add">
                <SelectValue placeholder="Choose a tag" />
              </SelectTrigger>
              <SelectContent>
                {available.map((tag) => (
                  <SelectItem key={tag.name} value={tag.name}>
                    {formatTagName(tag.name)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button
              variant="outline"
              disabled={!selected || addTag.isPending}
              onClick={() => {
                if (selected) {
                  addTag.mutate(selected, { onSuccess: () => setSelected("") })
                }
              }}
            >
              Add tag
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
```

## Partner pages
Create `frontend/src/pages/partner/dashboard-page.tsx`:
```tsx
import { CircleCheckIcon, GaugeIcon, PackageIcon, TruckIcon } from "lucide-react"
import { useState } from "react"

import { useMyShipments, usePartnerProfile } from "@/api/queries"
import { PageHeader } from "@/components/page-header"
import { ShipmentsTable } from "@/components/shipments-table"
import { StatCard } from "@/components/stat-card"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { isFinished } from "@/lib/format"

export function PartnerDashboardPage() {
  const [tab, setTab] = useState<"active" | "finished">("active")
  const shipments = useMyShipments("partner")
  const profile = usePartnerProfile()

  const all = shipments.data ?? []
  const active = all.filter((shipment) => !isFinished(shipment.status))
  const finished = all.filter((shipment) => isFinished(shipment.status))
  const delivered = finished.filter((shipment) => shipment.status === "delivered")
  const visible = tab === "active" ? active : finished

  return (
    <>
      <PageHeader
        title="Deliveries"
        description="Shipments assigned to you, update them as you go"
      />

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
        <StatCard title="Active" value={active.length} icon={<TruckIcon />} />
        <StatCard
          title="Capacity used"
          value={`${active.length} / ${profile.data?.max_handling_capacity ?? "-"}`}
          icon={<GaugeIcon />}
        />
        <StatCard title="Delivered" value={delivered.length} icon={<CircleCheckIcon />} />
      </div>

      <Card>
        <CardHeader>
          <Tabs value={tab} onValueChange={(value) => setTab(value as typeof tab)}>
            <TabsList>
              <TabsTrigger value="active">Active ({active.length})</TabsTrigger>
              <TabsTrigger value="finished">Finished ({finished.length})</TabsTrigger>
            </TabsList>
          </Tabs>
        </CardHeader>
        <CardContent>
          {shipments.isPending ? (
            <Skeleton className="h-32 w-full" />
          ) : visible.length === 0 ? (
            <Empty>
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <PackageIcon />
                </EmptyMedia>
                <EmptyTitle>Nothing here</EmptyTitle>
                <EmptyDescription>
                  New shipments to your zip codes show up here automatically.
                </EmptyDescription>
              </EmptyHeader>
            </Empty>
          ) : (
            <ShipmentsTable shipments={visible} basePath="/partner/shipments" />
          )}
        </CardContent>
      </Card>
    </>
  )
}
```
Create `frontend/src/pages/partner/shipment-page.tsx`:
```tsx
import { zodResolver } from "@hookform/resolvers/zod"
import { REGEXP_ONLY_DIGITS } from "input-otp"
import { ScanQrCodeIcon } from "lucide-react"
import { lazy, Suspense, useState } from "react"
import { Controller, useForm } from "react-hook-form"
import { useParams } from "react-router"
import { z } from "zod"

import type { ShipmentRead } from "@/api/generated"
import {
  useResendCode,
  useShipment,
  useUpdateShipment,
  useVerifyDelivery,
} from "@/api/queries"
import { FormField } from "@/components/form-field"
import { PageHeader } from "@/components/page-header"
import { ShipmentDetails } from "@/components/shipment-details"
import { ShipmentTimeline } from "@/components/shipment-timeline"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { FieldError, FieldGroup } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { InputOTP, InputOTPGroup, InputOTPSlot } from "@/components/ui/input-otp"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import { Textarea } from "@/components/ui/textarea"
import { isFinished, STATUS_LABELS } from "@/lib/format"

// The scanner library is big and only needed here, so it's downloaded
// the first time someone opens the scanner (code splitting)
const QrScannerDialog = lazy(() =>
  import("@/components/qr-scanner-dialog").then((module) => ({
    default: module.QrScannerDialog,
  })),
)

export function PartnerShipmentPage() {
  const { id = "" } = useParams()
  const { data: shipment, isPending, isError } = useShipment(id)

  if (isPending) {
    return <Skeleton className="h-96 w-full" />
  }
  if (isError) {
    return <p className="text-muted-foreground">This shipment couldn't be loaded.</p>
  }

  return (
    <>
      <PageHeader title="Delivery" description="Update the client on every step" />
      <div className="grid gap-6 lg:grid-cols-[3fr_2fr]">
        <div className="flex flex-col gap-6">
          <ShipmentDetails shipment={shipment} />
          {shipment.status === "out_for_delivery" && <DeliveryCard id={shipment.id} />}
          {!isFinished(shipment.status) && <UpdateCard shipment={shipment} />}
        </div>
        <ShipmentTimeline events={shipment.timeline} />
      </div>
    </>
  )
}

// "delivered" needs the client's code, so it's not in this list
const PARTNER_STATUSES = ["in_transit", "out_for_delivery"] as const

const updateSchema = z
  .object({
    status: z.enum(PARTNER_STATUSES).optional(),
    location: z.number().int().positive().optional(),
    description: z.string(),
    estimated_delivery: z.string(),
  })
  .refine(
    (values) =>
      values.status || values.location || values.description || values.estimated_delivery,
    { message: "Change at least one field", path: ["root"] },
  )

type UpdateValues = z.infer<typeof updateSchema>

function UpdateCard({ shipment }: { shipment: ShipmentRead }) {
  const updateShipment = useUpdateShipment(shipment.id)
  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<UpdateValues>({
    resolver: zodResolver(updateSchema),
    defaultValues: { description: "", estimated_delivery: "" },
  })

  function onSubmit(values: UpdateValues) {
    updateShipment.mutate(
      {
        status: values.status,
        location: values.location,
        description: values.description || undefined,
        // datetime-local gives local time without a timezone, the API needs one
        estimated_delivery: values.estimated_delivery
          ? new Date(values.estimated_delivery).toISOString()
          : undefined,
      },
      { onSuccess: () => reset() },
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Update progress</CardTitle>
        <CardDescription>The client gets an email when the status changes</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit(onSubmit)} noValidate>
          <FieldGroup>
            <div className="grid gap-4 sm:grid-cols-2">
              <FormField id="status" label="Status" error={errors.status}>
                {/* Select isn't a normal <input>, Controller connects it to the form */}
                <Controller
                  control={control}
                  name="status"
                  render={({ field }) => (
                    <Select value={field.value ?? ""} onValueChange={field.onChange}>
                      <SelectTrigger id="status" className="w-full">
                        <SelectValue placeholder="No change" />
                      </SelectTrigger>
                      <SelectContent>
                        {PARTNER_STATUSES.map((status) => (
                          <SelectItem key={status} value={status}>
                            {STATUS_LABELS[status]}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
              </FormField>
              <FormField id="location" label="Current zip code" error={errors.location}>
                <Input
                  id="location"
                  type="number"
                  placeholder="11002"
                  {...register("location", {
                    // Empty means "no change", not 0 or NaN
                    setValueAs: (value) => (value === "" ? undefined : Number(value)),
                  })}
                />
              </FormField>
            </div>
            <FormField id="description" label="Note (optional)">
              <Textarea
                id="description"
                placeholder="Arrived at the hub"
                {...register("description")}
              />
            </FormField>
            <FormField id="estimated_delivery" label="New estimated delivery (optional)">
              <Input
                id="estimated_delivery"
                type="datetime-local"
                {...register("estimated_delivery")}
              />
            </FormField>
            <FieldError errors={[errors.root]} />
            <Button type="submit" className="self-start" disabled={updateShipment.isPending}>
              {updateShipment.isPending && <Spinner />}
              Save update
            </Button>
          </FieldGroup>
        </form>
      </CardContent>
    </Card>
  )
}

function DeliveryCard({ id }: { id: string }) {
  const [code, setCode] = useState("")
  const [scanning, setScanning] = useState(false)
  const verify = useVerifyDelivery(id)
  const resend = useResendCode(id)

  function confirm(value: string) {
    verify.mutate(value, { onError: () => setCode("") })
  }

  return (
    <Card className="border-amber-300">
      <CardHeader>
        <CardTitle>Confirm delivery</CardTitle>
        <CardDescription>
          Ask the client for the 6 digit code from their email or SMS, or scan the QR
          code in their email.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <InputOTP
          maxLength={6}
          pattern={REGEXP_ONLY_DIGITS}
          value={code}
          onChange={setCode}
          aria-label="Delivery code"
        >
          <InputOTPGroup>
            {[0, 1, 2, 3, 4, 5].map((index) => (
              <InputOTPSlot key={index} index={index} />
            ))}
          </InputOTPGroup>
        </InputOTP>
        <div className="flex flex-wrap gap-2">
          <Button disabled={code.length !== 6 || verify.isPending} onClick={() => confirm(code)}>
            {verify.isPending && <Spinner />}
            Confirm delivery
          </Button>
          <Button variant="outline" onClick={() => setScanning(true)}>
            <ScanQrCodeIcon />
            Scan QR code
          </Button>
          <Button variant="ghost" disabled={resend.isPending} onClick={() => resend.mutate()}>
            Send a new code
          </Button>
        </div>
      </CardContent>
      {scanning && (
        <Suspense fallback={null}>
          <QrScannerDialog
            open
            onOpenChange={setScanning}
            onCode={(scanned) => {
              setScanning(false)
              setCode(scanned)
              confirm(scanned)
            }}
          />
        </Suspense>
      )}
    </Card>
  )
}
```
- **`Controller`:** shadcn's `Select` isn't a plain `<input>`, so `register` can't connect it. `Controller` connects any custom input to react-hook-form.
- **`setValueAs`** turns an empty "Current zip code" into `undefined`, which means "no change", instead of `0` or `NaN`.
- **`datetime-local`** gives local time without a timezone. `new Date(value).toISOString()` adds it, because your API requires an aware datetime (`AwareDatetime`).
- **`lazy()` + `Suspense` is code splitting.** The scanner library is about 150 kB and only partners use it, so the browser downloads it the first time someone opens the scanner. Everyone else never downloads it.

Create `frontend/src/pages/partner/profile-page.tsx`:
```tsx
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { usePartnerProfile, useUpdatePartner } from "@/api/queries"
import { FormField } from "@/components/form-field"
import { PageHeader } from "@/components/page-header"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { FieldGroup } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import { parseZipCodes, ZIP_CODE_LIST } from "@/lib/format"

const profileSchema = z.object({
  serviceable_zip_codes: z
    .string()
    .regex(ZIP_CODE_LIST, "Zip codes separated by commas, like 11001, 11002"),
  max_handling_capacity: z.number({ error: "Enter a number" }).int().min(1),
})

type ProfileValues = z.infer<typeof profileSchema>

export function PartnerProfilePage() {
  const profile = usePartnerProfile()
  const updatePartner = useUpdatePartner()

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ProfileValues>({
    resolver: zodResolver(profileSchema),
    // `values` fills the form when the profile arrives from the API
    values: profile.data && {
      serviceable_zip_codes: profile.data.serviceable_zip_codes.join(", "),
      max_handling_capacity: profile.data.max_handling_capacity,
    },
  })

  function onSubmit(values: ProfileValues) {
    updatePartner.mutate({
      serviceable_zip_codes: parseZipCodes(values.serviceable_zip_codes),
      max_handling_capacity: values.max_handling_capacity,
    })
  }

  return (
    <>
      <PageHeader title="Profile" description="Where you deliver and how much you can carry" />
      <Card className="max-w-2xl">
        <CardHeader>
          <CardTitle>{profile.data?.name ?? <Skeleton className="h-5 w-40" />}</CardTitle>
          <CardDescription>{profile.data?.email}</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} noValidate>
            <FieldGroup>
              <FormField
                id="serviceable_zip_codes"
                label="Zip codes you deliver to"
                error={errors.serviceable_zip_codes}
                description="New shipments to these zip codes can be assigned to you"
              >
                <Input
                  id="serviceable_zip_codes"
                  aria-invalid={!!errors.serviceable_zip_codes}
                  {...register("serviceable_zip_codes")}
                />
              </FormField>
              <FormField
                id="max_handling_capacity"
                label="Shipments you can handle at once"
                error={errors.max_handling_capacity}
              >
                <Input
                  id="max_handling_capacity"
                  type="number"
                  aria-invalid={!!errors.max_handling_capacity}
                  {...register("max_handling_capacity", { valueAsNumber: true })}
                />
              </FormField>
              <Button
                type="submit"
                className="self-start"
                disabled={updatePartner.isPending || !profile.data}
              >
                {updatePartner.isPending && <Spinner />}
                Save
              </Button>
            </FieldGroup>
          </form>
        </CardContent>
      </Card>
    </>
  )
}
```
The **`values`** option fills the form once the profile arrives from the API, and keeps it in sync if it changes.

---

# Part 9: Routes and the entry point

Create `frontend/src/routes.tsx`:
```tsx
import { Route, Routes } from "react-router"

import { RequireAuth } from "@/auth/require-auth"
import { DashboardLayout } from "@/layouts/dashboard-layout"
import { HomePage } from "@/pages/home-page"
import { LoginPage } from "@/pages/login-page"
import { NotFoundPage } from "@/pages/not-found-page"
import { PartnerDashboardPage } from "@/pages/partner/dashboard-page"
import { PartnerProfilePage } from "@/pages/partner/profile-page"
import { PartnerShipmentPage } from "@/pages/partner/shipment-page"
import { SellerDashboardPage } from "@/pages/seller/dashboard-page"
import { NewShipmentPage } from "@/pages/seller/new-shipment-page"
import { SellerShipmentPage } from "@/pages/seller/shipment-page"
import { SignupPage } from "@/pages/signup-page"
import { TrackPage } from "@/pages/track-page"

// Which page shows for which URL. A route without a path only wraps its children
export function AppRoutes() {
  return (
    <Routes>
      {/* Public */}
      <Route path="/" element={<HomePage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route path="/track/:id" element={<TrackPage />} />

      {/* Sellers only, inside the sidebar layout */}
      <Route element={<RequireAuth role="seller" />}>
        <Route element={<DashboardLayout />}>
          <Route path="/seller" element={<SellerDashboardPage />} />
          <Route path="/seller/shipments/new" element={<NewShipmentPage />} />
          <Route path="/seller/shipments/:id" element={<SellerShipmentPage />} />
        </Route>
      </Route>

      {/* Delivery partners only */}
      <Route element={<RequireAuth role="partner" />}>
        <Route element={<DashboardLayout />}>
          <Route path="/partner" element={<PartnerDashboardPage />} />
          <Route path="/partner/shipments/:id" element={<PartnerShipmentPage />} />
          <Route path="/partner/profile" element={<PartnerProfilePage />} />
        </Route>
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
```
**Nested routes:** a `<Route>` without a `path` only wraps its children:
- **`RequireAuth`** checks the login.
- **`DashboardLayout`** draws the sidebar.
- **The page** appears where the parent renders `<Outlet />`.

Replace the whole of `frontend/src/main.tsx`:
```tsx
import "@/index.css"

import { QueryClientProvider } from "@tanstack/react-query"
import { ReactQueryDevtools } from "@tanstack/react-query-devtools"
import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { BrowserRouter } from "react-router"

import { queryClient } from "@/api/query-client"
import { AuthProvider } from "@/auth/auth-provider"
import { Toaster } from "@/components/ui/sonner"
import { TooltipProvider } from "@/components/ui/tooltip"
import { AppRoutes } from "@/routes"

// Providers wrap the whole app, so every component can use what they give:
// cached API data, the login session, tooltips, and the current URL
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <TooltipProvider>
          <BrowserRouter>
            <AppRoutes />
          </BrowserRouter>
          <Toaster richColors position="top-right" />
        </TooltipProvider>
      </AuthProvider>
      {/* A panel to inspect the cache, only in development */}
      <ReactQueryDevtools />
    </QueryClientProvider>
  </StrictMode>,
)
```
**The order of the providers matters.** `AuthProvider` uses `useQueryClient()` to clear the cache on logout, so it must be **inside** `QueryClientProvider`.

## Check it builds
In `frontend/`:
```bash
npm run lint      # should print nothing but "> oxlint"
npm run build     # TypeScript check + production build
```
The build prints `Some chunks are larger than 500 kB`. That's a hint, not an error: the main file is about 240 kB gzipped, which is fine for a dashboard. If a type error appears instead, a file has a typo. Send it to me.

---

# Part 10: Run and try everything

You need 4 terminals. Postgres, Redis and RabbitMQ run as Homebrew services. Check with `brew services list`.

| Terminal | Folder | Command |
|---|---|---|
| 1 | project root | `celery -A app.worker.celery_app worker --pool=threads --concurrency=4 --loglevel=INFO` |
| 2 | project root | `fastapi dev` |
| 3 | `frontend/` | `npm run dev` |
| 4 | anywhere | for git, and for regenerating the client |

Open **http://localhost:5173**.

**Test the app in this order.** Every endpoint gets used.
1. **Sign up as a seller.** You land on your empty dashboard, and the sidebar shows your name from `/seller/me`.
2. **Create a shipment to a zip code nobody serves.** You get a red toast: "No delivery partner available".
3. **Open a private window** (Cmd + Shift + N), which has a separate localStorage, so it's a separate login. **Sign up as a partner** for that zip code. Use your own email as the client email in the next step, so you receive the emails.
4. **As the seller, create the shipment again.** You land on its page. Add **Fragile** and **Gift**, then remove Gift. Click **Copy tracking link**.
5. **Seller dashboard:** check the stats, the status tabs, and the tag filter (this uses `/tag/shipments`).
6. **Paste the tracking link** into a third window, without logging in. That's the public client page.
7. **As the partner:** open the shipment. You see the handling instruction for Fragile. Set **In transit** with a zip code and a note. Then set **Out for delivery**. The worker emails the client a **code and a QR image**.
8. **Type a wrong code** (000000). You get "Wrong code, 4 attempts left". Click **Send a new code** twice. The second click gives the 60-second cooldown message.
9. **Scan the QR code from the newest email**, or type its code. The shipment becomes **Delivered**.
10. **As the seller:** create another shipment and **cancel** it through the confirmation dialog.
11. **Partner profile:** change the capacity, save, and refresh. It stays.
12. **Log out** from the user menu at the bottom of the sidebar. Opening `/seller` now goes to the login page.

**React Query Devtools:** the round icon in the bottom-right corner opens a panel with every cached query. Watch the keys appear and change as you click around. It's the best way to *see* React Query working.

### Testing the QR scanner
- **On your Mac:** open the email on your **phone** and hold the phone's screen up to the laptop webcam. `localhost` is allowed to use the camera.
- **Run the app on your phone:**
  1. Stop `npm run dev` and run **`npm run dev:phone`** instead.
  2. It prints a `Network: https://192.168.x.x:5173` address. Open that on your phone, on the same Wi-Fi.
  3. You'll see a certificate warning, because the dev certificate is self-signed. Choose **Advanced → Proceed** (Chrome) or **Show Details → visit this website** (Safari).
  4. If macOS asks to allow incoming connections for node, click **Allow**.
  5. Log in as the partner, open the shipment, and scan the QR shown in the email on your laptop screen.

---

# Part 11: Going to production

These are notes for later, not needed now.
- **`npm run build`** creates `frontend/dist/`: plain HTML, JS and CSS files that any web server can serve.
- **Same domain (most common):** nginx serves `dist/` and forwards `/api/` to FastAPI, exactly like our Vite proxy. No CORS is needed.
- **Different domains:** set `VITE_API_URL=https://api.example.com` in `frontend/.env` **before** building, and put the frontend's address in the backend's `CORS_ORIGINS`.
- **The web server must answer every unknown path with `index.html`.** That's called "SPA fallback". Otherwise refreshing `/seller/shipments/123` gives a 404.
- **Every `VITE_` variable ends up inside the JS files that anyone can read.** Never put secrets in the frontend.

---

# Part 12: What I tested

**Backend:**
- 79 pytest tests pass (8 new).
- Ruff and Mypy are clean for `app/` and `tests/`.
- The operation ids are unique and short.

**Frontend:**
- **Build and lint:** `tsc` passes in strict mode, the build succeeds, and Oxlint shows 0 warnings.
- **Replayed from zero:** I re-ran every command in Part 2 in an empty folder, added the files, and got the identical file list, components and packages. That build passed too.

**A real browser (Playwright + Chromium) ran 30 checks, all passing, with no browser console errors:**
- **Signup:** validation messages, success with automatic login, the 409 message for a used email
- **New shipment:** the form rules (weight at most 25, phone format), the 409 toast when no partner serves the zip code, the success toast, landing on the shipment's page
- **Tags and links:** adding and removing tags, copying the tracking link (checked in the clipboard)
- **Seller dashboard:** stats, status tabs, the tag filter
- **Tracking page:** the public page, and a wrong id (an inline message, no toast)
- **Partner updates:**
  - an empty update is refused
  - in transit with a note and zip code
  - a new estimated delivery from `datetime-local` saved with a timezone
- **Delivery:**
  - out for delivery sends an email **with an inline QR**
  - a wrong code shows the attempts left
  - "send a new code" works, and the cooldown blocks the second try
- **The QR scan, with a fake camera:** the camera played the QR image taken from the real captured email. The browser decoded it, verified it, and the shipment became Delivered.
- **Cancel and profile:** cancel through the dialog, then the filter; the profile form is prefilled and the save persists
- **Guards and sessions:**
  - a partner opening `/seller` is sent to `/partner`
  - log out clears the session, and the old token gets 401 from the API
  - a wrong password shows the API's message
  - after logging in you return to the page that needed it
  - a broken token goes to "session expired"
  - an unknown URL shows "not found"
- **Phone size:** the 2-column stats, the drawer opening and closing on navigation, the shipment page
- **HTTPS phone mode:** `npm run dev:phone` serves HTTPS on the network address, and the API proxy works through it

**Bugs the tests found, already fixed in this guide:**
- The Micro QR (1.3)
- The camera size (Part 5)

**I could not test:**
- **A real phone and your real webcam.** I used a fake camera, so please try Part 10.
- **How Gmail displays the QR image.** I checked the email's structure (`multipart/related`, `Content-ID`, `cid:` in the HTML), which is the standard way Gmail supports, but I didn't view it in Gmail.

---

# Part 13: Best practices used here

- **Generated API types.** The backend is the single source of truth, and the frontend can't drift from it without a TypeScript error.
- **Server state vs client state.** React Query for API data, a small Context for the session, no Redux.
- **One place for each concern:** the auth header (`securityWorker`), expired sessions (the interceptor), error messages (`getErrorMessage` and the global toasts), cache keys (`queryKeys`).
- **Every page handles loading, error and empty states.**
- **Validate in the frontend for speed and in the backend for safety.**
- **Responsive by default:** phone-first classes, and a sidebar that becomes a drawer.
- **Accessible:** labels on every input, `aria-invalid` on wrong fields, confirmation before destructive actions, real links for navigation.
- **Code splitting** for the big, rarely used scanner.
- **Development proxy** instead of CORS, and HTTPS for camera testing on phones.
- **Don't edit generated or copied library code** (`generated.ts`, `components/ui/`) unless you mean to. Lint your own code.

---

# Part 14: Interview questions

- **What's the difference between server state and client state?** Server state belongs to the backend (shipments). It's fetched, cached and can go stale, and React Query manages it. Client state exists only in the browser (the session, an open dialog), and `useState` or Context manages it.
- **Why React Query instead of `useEffect` + `fetch`?** It handles caching, request deduplication, retries, background refresh, loading and error states, and invalidation. Writing all of that by hand in effects is long and easy to get wrong.
- **What does invalidating a query do?** It marks the cached data as stale. Queries that are on screen refetch right away, and the others refetch the next time they're used.
- **Where do you store a JWT in a SPA?** localStorage is simple but readable by injected scripts. An httpOnly cookie is safer against XSS but needs CSRF protection. Either way, keep tokens short-lived and protect against XSS.
- **Does protecting a route in React secure the data?** No. It's only for the user experience. The API must check the token and the permissions on every request.
- **Why a dev-server proxy?** The browser sees one origin, so there are no CORS preflights in development, and it matches how production usually works behind nginx.
- **What is `key` in a list for?** It lets React match items between renders, so it updates the right row instead of redrawing everything.
- **Controlled vs uncontrolled inputs?** A controlled input's value lives in React state (`value` plus `onChange`). An uncontrolled input keeps its own value, and react-hook-form reads it through `register`. That's why it doesn't redraw on every key press.
- **What is code splitting?** Splitting the JavaScript into chunks that load when needed (`lazy()` + `Suspense`), so the first page loads faster.
- **Why generate the API client?** Types and methods always match the backend, there's less hand-written code, and backend changes become build errors instead of production bugs.

---

# Part 15: When you're done

Tell me, and I'll:
1. **run the backend tests, the frontend build and lint, and the browser checks on your version**, then
2. **commit and push**: the backend changes, `frontend/` (not `node_modules/` or `dist/`, which `frontend/.gitignore` already excludes), and this guide.
