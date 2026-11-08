/* eslint-disable */
/* tslint:disable */
// @ts-nocheck
/*
 * ---------------------------------------------------------------
 * ## THIS FILE WAS GENERATED VIA SWAGGER-TYPESCRIPT-API        ##
 * ##                                                           ##
 * ## AUTHOR: acacode                                           ##
 * ## SOURCE: https://github.com/acacode/swagger-typescript-api ##
 * ---------------------------------------------------------------
 */

/** TagName */
export type TagName =
  | "express"
  | "standard"
  | "fragile"
  | "heavy"
  | "international"
  | "temperature_controlled"
  | "gift";

/** ShipmentStatus */
export type ShipmentStatus =
  | "placed"
  | "in_transit"
  | "out_for_delivery"
  | "delivered"
  | "cancelled";

/** Body_login_delivery_partner */
export interface BodyLoginDeliveryPartner {
  /** Grant Type */
  grant_type?: string | null;
  /** Username */
  username: string;
  /**
   * Password
   * @format password
   */
  password: string;
  /**
   * Scope
   * @default ""
   */
  scope?: string;
  /** Client Id */
  client_id?: string | null;
  /**
   * Client Secret
   * @format password
   */
  client_secret?: string | null;
}

/** Body_login_seller */
export interface BodyLoginSeller {
  /** Grant Type */
  grant_type?: string | null;
  /** Username */
  username: string;
  /**
   * Password
   * @format password
   */
  password: string;
  /**
   * Scope
   * @default ""
   */
  scope?: string;
  /** Client Id */
  client_id?: string | null;
  /**
   * Client Secret
   * @format password
   */
  client_secret?: string | null;
}

/** DeliveryPartnerCreate */
export interface DeliveryPartnerCreate {
  /** Name */
  name: string;
  /**
   * Email
   * @format email
   */
  email: string;
  /**
   * Serviceable Zip Codes
   * Zip codes this partner delivers to
   */
  serviceable_zip_codes: number[];
  /**
   * Max Handling Capacity
   * Most shipments the partner handles at once
   */
  max_handling_capacity: number;
  /** Password */
  password: string;
}

/** DeliveryPartnerRead */
export interface DeliveryPartnerRead {
  /** Name */
  name: string;
  /**
   * Email
   * @format email
   */
  email: string;
  /**
   * Serviceable Zip Codes
   * Zip codes this partner delivers to
   */
  serviceable_zip_codes: number[];
  /**
   * Max Handling Capacity
   * Most shipments the partner handles at once
   */
  max_handling_capacity: number;
}

/** DeliveryPartnerUpdate */
export interface DeliveryPartnerUpdate {
  /** Serviceable Zip Codes */
  serviceable_zip_codes?: number[] | null;
  /** Max Handling Capacity */
  max_handling_capacity?: number | null;
}

/**
 * ErrorResponse
 * The body of every error the API returns on purpose
 */
export interface ErrorResponse {
  /** Detail */
  detail: string;
}

/** HTTPValidationError */
export interface HTTPValidationError {
  /** Detail */
  detail?: ValidationError[];
}

/**
 * Message
 * A short message that confirms the action worked
 */
export interface Message {
  /** Detail */
  detail: string;
}

/** SellerCreate */
export interface SellerCreate {
  /** Name */
  name: string;
  /**
   * Email
   * @format email
   */
  email: string;
  /** Address */
  address?: string | null;
  /**
   * Zip Code
   * Where the seller's shipments start
   */
  zip_code: number;
  /** Password */
  password: string;
}

/** SellerRead */
export interface SellerRead {
  /** Name */
  name: string;
  /**
   * Email
   * @format email
   */
  email: string;
  /** Address */
  address?: string | null;
  /** Zip Code */
  zip_code?: number | null;
}

/**
 * ShipmentCreate
 * A new shipment, a delivery partner is assigned automatically
 */
export interface ShipmentCreate {
  /**
   * Content
   * What is inside the package
   */
  content: string;
  /**
   * Weight
   * Weight in kg
   * @exclusiveMin 0
   * @max 25
   */
  weight: number;
  /**
   * Destination
   * Zip code to deliver to
   */
  destination: number;
  /**
   * Client Contact Email
   * Gets the tracking link and the delivery code
   * @format email
   */
  client_contact_email: string;
  /**
   * Client Contact Phone
   * Optional, in international format. Gets the code by SMS
   */
  client_contact_phone?: string | null;
}

/** ShipmentEvent */
export interface ShipmentEvent {
  /**
   * Id
   * @format uuid
   */
  id: string;
  /**
   * Created At
   * @format date-time
   */
  created_at: string;
  /** Location */
  location: number;
  status: ShipmentStatus;
  /** Description */
  description?: string | null;
  /**
   * Shipment Id
   * @format uuid
   */
  shipment_id: string;
}

/**
 * ShipmentRead
 * A shipment with its full history, newest event last
 */
export interface ShipmentRead {
  /**
   * Content
   * What is inside the package
   */
  content: string;
  /**
   * Weight
   * Weight in kg
   * @exclusiveMin 0
   * @max 25
   */
  weight: number;
  /**
   * Destination
   * Zip code to deliver to
   */
  destination: number;
  /**
   * Id
   * @format uuid
   */
  id: string;
  status: ShipmentStatus | null;
  /** Timeline */
  timeline: ShipmentEvent[];
  /** Tags */
  tags: TagRead[];
  /**
   * Estimated Delivery
   * @format date-time
   */
  estimated_delivery: string;
}

/**
 * ShipmentUpdate
 * Send only the fields that changed, at least one
 */
export interface ShipmentUpdate {
  /**
   * Location
   * Zip code where the shipment is now
   */
  location?: number | null;
  /** Description */
  description?: string | null;
  /** Can't be `delivered`, use /shipment/verify for that */
  status?: ShipmentStatus | null;
  /**
   * Estimated Delivery
   * Must include a timezone
   */
  estimated_delivery?: string | null;
}

/** ShipmentVerify */
export interface ShipmentVerify {
  /**
   * Code
   * The 6 digit code the client received
   * @pattern ^\d{6}$
   */
  code: string;
}

/** TagRead */
export interface TagRead {
  name: TagName;
  /** Instruction */
  instruction: string;
}

/** Token */
export interface Token {
  /**
   * Access Token
   * Send it as `Authorization: Bearer <token>`
   */
  access_token: string;
  /**
   * Token Type
   * @default "bearer"
   */
  token_type?: string;
  /**
   * Type
   * @deprecated
   * @default "jwt"
   */
  type?: string;
}

/** ValidationError */
export interface ValidationError {
  /** Location */
  loc: (string | number)[];
  /** Message */
  msg: string;
  /** Error Type */
  type: string;
  /** Input */
  input?: any;
  /** Context */
  ctx?: object;
}

import type {
  AxiosInstance,
  AxiosRequestConfig,
  HeadersDefaults,
  ResponseType,
} from "axios";
import axios from "axios";

export type QueryParamsType = Record<string | number, any>;

export interface FullRequestParams
  extends Omit<AxiosRequestConfig, "data" | "params" | "url" | "responseType"> {
  /** set parameter to `true` for call `securityWorker` for this request */
  secure?: boolean;
  /** request path */
  path: string;
  /** content type of request body */
  type?: ContentType;
  /** query params */
  query?: QueryParamsType;
  /** format of response (i.e. response.json() -> format: "json") */
  format?: ResponseType;
  /** request body */
  body?: unknown;
}

export type RequestParams = Omit<
  FullRequestParams,
  "body" | "method" | "query" | "path"
>;

export interface ApiConfig<SecurityDataType = unknown>
  extends Omit<AxiosRequestConfig, "data" | "cancelToken"> {
  securityWorker?: (
    securityData: SecurityDataType | null,
  ) => Promise<AxiosRequestConfig | void> | AxiosRequestConfig | void;
  secure?: boolean;
  format?: ResponseType;
}

export type ContentType =
  | "application/json"
  | "application/vnd.api+json"
  | "multipart/form-data"
  | "application/x-www-form-urlencoded"
  | "text/plain";

export class HttpClient<SecurityDataType = unknown> {
  public instance: AxiosInstance;
  private securityData: SecurityDataType | null = null;
  private securityWorker?: ApiConfig<SecurityDataType>["securityWorker"];
  private secure?: boolean;
  private format?: ResponseType;

  constructor({
    securityWorker,
    secure,
    format,
    ...axiosConfig
  }: ApiConfig<SecurityDataType> = {}) {
    this.instance = axios.create({
      ...axiosConfig,
      baseURL: axiosConfig.baseURL || "",
    });
    this.secure = secure;
    this.format = format;
    this.securityWorker = securityWorker;
  }

  public setSecurityData = (data: SecurityDataType | null) => {
    this.securityData = data;
  };

  protected mergeRequestParams(
    params1: AxiosRequestConfig,
    params2?: AxiosRequestConfig,
  ): AxiosRequestConfig {
    const method = params1.method || (params2 && params2.method);

    return {
      ...this.instance.defaults,
      ...params1,
      ...(params2 || {}),
      headers: {
        ...((method &&
          this.instance.defaults.headers[
            method.toLowerCase() as keyof HeadersDefaults
          ]) ||
          {}),
        ...(params1.headers || {}),
        ...((params2 && params2.headers) || {}),
      },
    };
  }

  protected stringifyFormItem(formItem: unknown) {
    if (typeof formItem === "object" && formItem !== null) {
      return JSON.stringify(formItem);
    } else {
      return `${formItem}`;
    }
  }

  protected createFormData(input: Record<string, unknown>): FormData {
    if (input instanceof FormData) {
      return input;
    }
    return Object.keys(input || {}).reduce((formData, key) => {
      const property = input[key];
      const propertyContent: any[] =
        property instanceof Array ? property : [property];

      for (const formItem of propertyContent) {
        const isFileType = formItem instanceof Blob || formItem instanceof File;
        formData.append(
          key,
          isFileType ? formItem : this.stringifyFormItem(formItem),
        );
      }

      return formData;
    }, new FormData());
  }

  public request = async <T = any, _E = any>({
    secure,
    path,
    type,
    query,
    format,
    body,
    ...params
  }: FullRequestParams): Promise<T> => {
    const secureParams =
      ((typeof secure === "boolean" ? secure : this.secure) &&
        this.securityWorker &&
        (await this.securityWorker(this.securityData))) ||
      {};
    const requestParams = this.mergeRequestParams(params, secureParams);
    const responseFormat = format || this.format || undefined;

    if (
      type === "multipart/form-data" &&
      body &&
      body !== null &&
      typeof body === "object"
    ) {
      body = this.createFormData(body as Record<string, unknown>);
    }

    if (
      type === "text/plain" &&
      body &&
      body !== null &&
      typeof body !== "string"
    ) {
      body = JSON.stringify(body);
    }

    return this.instance
      .request({
        ...requestParams,
        headers: {
          ...(requestParams.headers || {}),
          ...(type ? { "Content-Type": type } : {}),
        },
        params: query,
        responseType: responseFormat,
        data: body,
        url: path,
      })
      .then((response) => response.data);
  };
}

/**
 * @title FastShip API
 * @version 0.1.0
 * @termsOfService https://fastship.example.com/terms
 * @contact FastShip Support <support@fastship.example.com> (https://fastship.example.com/support)
 *
 *
 * Ship packages from **sellers** to **clients** through **delivery partners**.
 *
 * ## How to use it
 * 1. Sign up as a seller (`POST /seller/signup`) or a partner (`POST /partner/signup`)
 * 2. Log in with the **Authorize** button, or call `/seller/token` / `/partner/token`
 * 3. Sellers create shipments, partners update them until delivery
 *
 * ## Errors
 * Every error has the same body: `{"detail": "what went wrong"}`.
 * Validation errors (422) list each wrong field instead.
 */
export class Api<
  SecurityDataType extends unknown,
> extends HttpClient<SecurityDataType> {
  shipment = {
    /**
     * @description Anyone with the id can read the shipment, like a tracking number.
     *
     * @tags Shipment
     * @name GetShipment
     * @summary Get a shipment
     * @request GET:/shipment/
     */
    getShipment: (
      query: {
        /**
         * Id
         * The shipment's id, returned when it was created
         * @format uuid
         */
        id: string;
      },
      params: RequestParams = {},
    ) =>
      this.request<ShipmentRead, ErrorResponse | HTTPValidationError>({
        path: `/shipment/`,
        method: "GET",
        query: query,
        format: "json",
        ...params,
      }),

    /**
     * @description The seller creates a shipment. A delivery partner who serves the destination zip code is assigned, and the client gets an email with the tracking link. Fails with **409** if no partner serves that zip code or all are full.
     *
     * @tags Shipment
     * @name SubmitShipment
     * @summary Create a shipment
     * @request POST:/shipment/
     * @secure
     */
    submitShipment: (data: ShipmentCreate, params: RequestParams = {}) =>
      this.request<ShipmentRead, ErrorResponse | HTTPValidationError>({
        path: `/shipment/`,
        method: "POST",
        body: data,
        secure: true,
        type: "application/json",
        format: "json",
        ...params,
      }),

    /**
     * @description The assigned partner adds a new event: location, status or note.
     *
     * @tags Shipment
     * @name UpdateShipment
     * @summary Update a shipment's progress
     * @request PATCH:/shipment/
     * @secure
     */
    updateShipment: (
      query: {
        /**
         * Id
         * The shipment's id, returned when it was created
         * @format uuid
         */
        id: string;
      },
      data: ShipmentUpdate,
      params: RequestParams = {},
    ) =>
      this.request<ShipmentRead, ErrorResponse | HTTPValidationError>({
        path: `/shipment/`,
        method: "PATCH",
        query: query,
        body: data,
        secure: true,
        type: "application/json",
        format: "json",
        ...params,
      }),

    /**
     * @description The HTML page the client opens from the link in their email.
     *
     * @tags Shipment
     * @name GetTracking
     * @summary Tracking page
     * @request GET:/shipment/track
     */
    getTracking: (
      query: {
        /**
         * Id
         * The shipment's id, returned when it was created
         * @format uuid
         */
        id: string;
      },
      params: RequestParams = {},
    ) =>
      this.request<string, ErrorResponse | HTTPValidationError>({
        path: `/shipment/track`,
        method: "GET",
        query: query,
        ...params,
      }),

    /**
     * @description The partner enters the code the client received, which marks the shipment as delivered. After 5 wrong codes, a new code must be requested.
     *
     * @tags Shipment
     * @name VerifyDelivery
     * @summary Confirm delivery
     * @request POST:/shipment/verify
     * @secure
     */
    verifyDelivery: (
      query: {
        /**
         * Id
         * The shipment's id, returned when it was created
         * @format uuid
         */
        id: string;
      },
      data: ShipmentVerify,
      params: RequestParams = {},
    ) =>
      this.request<ShipmentRead, ErrorResponse | HTTPValidationError>({
        path: `/shipment/verify`,
        method: "POST",
        query: query,
        body: data,
        secure: true,
        type: "application/json",
        format: "json",
        ...params,
      }),

    /**
     * @description The old code stops working. Can be called once a minute.
     *
     * @tags Shipment
     * @name ResendVerificationCode
     * @summary Send the client a new code
     * @request POST:/shipment/resend-code
     * @secure
     */
    resendVerificationCode: (
      query: {
        /**
         * Id
         * The shipment's id, returned when it was created
         * @format uuid
         */
        id: string;
      },
      params: RequestParams = {},
    ) =>
      this.request<Message, ErrorResponse | HTTPValidationError>({
        path: `/shipment/resend-code`,
        method: "POST",
        query: query,
        secure: true,
        format: "json",
        ...params,
      }),

    /**
     * @description The seller cancels their shipment, if it isn't delivered yet.
     *
     * @tags Shipment
     * @name CancelShipment
     * @summary Cancel a shipment
     * @request POST:/shipment/cancel
     * @secure
     */
    cancelShipment: (
      query: {
        /**
         * Id
         * The shipment's id, returned when it was created
         * @format uuid
         */
        id: string;
      },
      params: RequestParams = {},
    ) =>
      this.request<ShipmentRead, ErrorResponse | HTTPValidationError>({
        path: `/shipment/cancel`,
        method: "POST",
        query: query,
        secure: true,
        format: "json",
        ...params,
      }),

    /**
     * @description **Use `POST /shipment/cancel` instead.** A GET request must not change data, browsers and tools may call it on their own. Kept so old clients still work.
     *
     * @tags Shipment
     * @name CancelShipmentOld
     * @summary Cancel a shipment (old)
     * @request GET:/shipment/cancel
     * @deprecated
     * @secure
     */
    cancelShipmentOld: (
      query: {
        /**
         * Id
         * The shipment's id, returned when it was created
         * @format uuid
         */
        id: string;
      },
      params: RequestParams = {},
    ) =>
      this.request<ShipmentRead, ErrorResponse | HTTPValidationError>({
        path: `/shipment/cancel`,
        method: "GET",
        query: query,
        secure: true,
        format: "json",
        ...params,
      }),

    /**
     * @description The seller adds a predefined tag, see `GET /tag/` for the list.
     *
     * @tags Shipment
     * @name AddTag
     * @summary Add a tag
     * @request POST:/shipment/tag
     * @secure
     */
    addTag: (
      query: {
        /**
         * Id
         * The shipment's id, returned when it was created
         * @format uuid
         */
        id: string;
        tag_name: TagName;
      },
      params: RequestParams = {},
    ) =>
      this.request<ShipmentRead, ErrorResponse | HTTPValidationError>({
        path: `/shipment/tag`,
        method: "POST",
        query: query,
        secure: true,
        format: "json",
        ...params,
      }),

    /**
     * @description The tag stays in the list, it's only removed from this shipment.
     *
     * @tags Shipment
     * @name RemoveTag
     * @summary Remove a tag
     * @request DELETE:/shipment/tag
     * @secure
     */
    removeTag: (
      query: {
        /**
         * Id
         * The shipment's id, returned when it was created
         * @format uuid
         */
        id: string;
        tag_name: TagName;
      },
      params: RequestParams = {},
    ) =>
      this.request<ShipmentRead, ErrorResponse | HTTPValidationError>({
        path: `/shipment/tag`,
        method: "DELETE",
        query: query,
        secure: true,
        format: "json",
        ...params,
      }),
  };
  seller = {
    /**
     * @description The password is stored hashed and is never returned.
     *
     * @tags Seller
     * @name RegisterSeller
     * @summary Register a seller
     * @request POST:/seller/signup
     */
    registerSeller: (data: SellerCreate, params: RequestParams = {}) =>
      this.request<SellerRead, ErrorResponse | HTTPValidationError>({
        path: `/seller/signup`,
        method: "POST",
        body: data,
        type: "application/json",
        format: "json",
        ...params,
      }),

    /**
     * @description Send the email as `username`. The token expires after a while.
     *
     * @tags Seller
     * @name LoginSeller
     * @summary Log in
     * @request POST:/seller/token
     */
    loginSeller: (data: BodyLoginSeller, params: RequestParams = {}) =>
      this.request<Token, ErrorResponse | HTTPValidationError>({
        path: `/seller/token`,
        method: "POST",
        body: data,
        type: "application/x-www-form-urlencoded",
        format: "json",
        ...params,
      }),

    /**
     * @description The frontend uses it to show who is logged in.
     *
     * @tags Seller
     * @name GetSellerProfile
     * @summary The logged in seller
     * @request GET:/seller/me
     * @secure
     */
    getSellerProfile: (params: RequestParams = {}) =>
      this.request<SellerRead, ErrorResponse>({
        path: `/seller/me`,
        method: "GET",
        secure: true,
        format: "json",
        ...params,
      }),

    /**
     * @description Every shipment the logged in seller created, newest first.
     *
     * @tags Seller
     * @name GetSellerShipments
     * @summary My shipments
     * @request GET:/seller/shipments
     * @secure
     */
    getSellerShipments: (params: RequestParams = {}) =>
      this.request<ShipmentRead[], ErrorResponse>({
        path: `/seller/shipments`,
        method: "GET",
        secure: true,
        format: "json",
        ...params,
      }),

    /**
     * @description The token stops working right away.
     *
     * @tags Seller
     * @name LogoutSeller
     * @summary Log out
     * @request GET:/seller/logout
     * @secure
     */
    logoutSeller: (params: RequestParams = {}) =>
      this.request<Message, ErrorResponse>({
        path: `/seller/logout`,
        method: "GET",
        secure: true,
        format: "json",
        ...params,
      }),
  };
  partner = {
    /**
     * @description The password is stored hashed and is never returned.
     *
     * @tags Delivery Partner
     * @name RegisterDeliveryPartner
     * @summary Register a delivery partner
     * @request POST:/partner/signup
     */
    registerDeliveryPartner: (
      data: DeliveryPartnerCreate,
      params: RequestParams = {},
    ) =>
      this.request<DeliveryPartnerRead, ErrorResponse | HTTPValidationError>({
        path: `/partner/signup`,
        method: "POST",
        body: data,
        type: "application/json",
        format: "json",
        ...params,
      }),

    /**
     * @description Send the email as `username`. The token expires after a while.
     *
     * @tags Delivery Partner
     * @name LoginDeliveryPartner
     * @summary Log in
     * @request POST:/partner/token
     */
    loginDeliveryPartner: (
      data: BodyLoginDeliveryPartner,
      params: RequestParams = {},
    ) =>
      this.request<Token, ErrorResponse | HTTPValidationError>({
        path: `/partner/token`,
        method: "POST",
        body: data,
        type: "application/x-www-form-urlencoded",
        format: "json",
        ...params,
      }),

    /**
     * @description The frontend uses it to show who is logged in and fill the profile form.
     *
     * @tags Delivery Partner
     * @name GetPartnerProfile
     * @summary The logged in partner
     * @request GET:/partner/me
     * @secure
     */
    getPartnerProfile: (params: RequestParams = {}) =>
      this.request<DeliveryPartnerRead, ErrorResponse>({
        path: `/partner/me`,
        method: "GET",
        secure: true,
        format: "json",
        ...params,
      }),

    /**
     * @description Every shipment assigned to the logged in partner, newest first.
     *
     * @tags Delivery Partner
     * @name GetPartnerShipments
     * @summary My assigned shipments
     * @request GET:/partner/shipments
     * @secure
     */
    getPartnerShipments: (params: RequestParams = {}) =>
      this.request<ShipmentRead[], ErrorResponse>({
        path: `/partner/shipments`,
        method: "GET",
        secure: true,
        format: "json",
        ...params,
      }),

    /**
     * @description Send only the fields that changed.
     *
     * @tags Delivery Partner
     * @name UpdateDeliveryPartner
     * @summary Update the logged in partner
     * @request PATCH:/partner/
     * @secure
     */
    updateDeliveryPartner: (
      data: DeliveryPartnerUpdate,
      params: RequestParams = {},
    ) =>
      this.request<DeliveryPartnerRead, ErrorResponse | HTTPValidationError>({
        path: `/partner/`,
        method: "PATCH",
        body: data,
        secure: true,
        type: "application/json",
        format: "json",
        ...params,
      }),

    /**
     * @description The token stops working right away.
     *
     * @tags Delivery Partner
     * @name LogoutDeliveryPartner
     * @summary Log out
     * @request GET:/partner/logout
     * @secure
     */
    logoutDeliveryPartner: (params: RequestParams = {}) =>
      this.request<Message, ErrorResponse>({
        path: `/partner/logout`,
        method: "GET",
        secure: true,
        format: "json",
        ...params,
      }),
  };
  tag = {
    /**
     * @description Every tag a seller can add, with its handling instruction.
     *
     * @tags Tag
     * @name GetTags
     * @summary List all tags
     * @request GET:/tag/
     */
    getTags: (params: RequestParams = {}) =>
      this.request<TagRead[], any>({
        path: `/tag/`,
        method: "GET",
        format: "json",
        ...params,
      }),

    /**
     * @description The logged in seller's shipments that have this tag, newest first.
     *
     * @tags Tag
     * @name GetShipmentsByTag
     * @summary My shipments with a tag
     * @request GET:/tag/shipments
     * @secure
     */
    getShipmentsByTag: (
      query: {
        tag_name: TagName;
      },
      params: RequestParams = {},
    ) =>
      this.request<ShipmentRead[], ErrorResponse | HTTPValidationError>({
        path: `/tag/shipments`,
        method: "GET",
        query: query,
        secure: true,
        format: "json",
        ...params,
      }),
  };
  time = {
    /**
     * No description
     *
     * @name GetCurrentTime
     * @summary Get Current Time
     * @request GET:/time
     */
    getCurrentTime: (params: RequestParams = {}) =>
      this.request<any, any>({
        path: `/time`,
        method: "GET",
        format: "json",
        ...params,
      }),
  };
  file = {
    /**
     * No description
     *
     * @name GetFile
     * @summary Get File
     * @request GET:/file
     */
    getFile: (params: RequestParams = {}) =>
      this.request<void, any>({
        path: `/file`,
        method: "GET",
        ...params,
      }),
  };
  timenow = {
    /**
     * No description
     *
     * @name GetTimeNow
     * @summary Get Time Now
     * @request GET:/timenow
     */
    getTimeNow: (params: RequestParams = {}) =>
      this.request<any, void>({
        path: `/timenow`,
        method: "GET",
        ...params,
      }),
  };
  utcnow = {
    /**
     * No description
     *
     * @name GetUtcTime
     * @summary Get Utc Time
     * @request GET:/utcnow
     */
    getUtcTime: (params: RequestParams = {}) =>
      this.request<any, any>({
        path: `/utcnow`,
        method: "GET",
        format: "json",
        ...params,
      }),
  };
  custom = {
    /**
     * No description
     *
     * @name GetCustomResponse
     * @summary Get Custom Response
     * @request GET:/custom
     */
    getCustomResponse: (params: RequestParams = {}) =>
      this.request<void, any>({
        path: `/custom`,
        method: "GET",
        ...params,
      }),
  };
}
