// Common API types
export interface ApiError {
  message: string
  status?: number
  code?: string
}

/**
 * Type-safe representation of API error responses.
 * Replaces unsafe `as { response?: { status?: number } }` casts.
 */
export interface ApiErrorResponse {
  response?: {
    status?: number;
    data?: {
      detail?: string;
      message?: string;
    };
  };
  message?: string;
}

/**
 * Type guard to safely check if an error is an API error response.
 * Use this instead of unsafe type assertions.
 *
 * @example
 * catch (error) {
 *   if (isApiError(error) && error.response?.status === 401) {
 *     // Handle unauthorized
 *   }
 * }
 */
export function isApiError(error: unknown): error is ApiErrorResponse {
  return (
    typeof error === 'object' &&
    error !== null &&
    ('response' in error || 'message' in error)
  );
}

/**
 * Safely extract status code from an error.
 * Returns undefined if the error doesn't have a status.
 *
 * Handles both error shapes in play: the custom `ApiError` thrown by the axios
 * interceptor (`lib/api/client.ts`) exposes the HTTP status at the top level
 * (`error.status`), while a raw axios error nests it under `error.response.status`.
 * Reading only the nested shape silently returns `undefined` for every intercepted
 * error — which broke the logged-out (401) detection behind the account avatar.
 */
export function getErrorStatus(error: unknown): number | undefined {
  if (typeof error !== 'object' || error === null) return undefined;
  const e = error as { status?: unknown; response?: { status?: unknown } };
  if (typeof e.status === 'number') return e.status;
  if (typeof e.response?.status === 'number') return e.response.status;
  return undefined;
}

/**
 * Safely extract error message from an error.
 */
export function getErrorMessage(error: unknown): string {
  if (isApiError(error)) {
    return (
      error.response?.data?.detail ||
      error.response?.data?.message ||
      error.message ||
      'An unexpected error occurred'
    );
  }
  if (error instanceof Error) {
    return error.message;
  }
  return 'An unexpected error occurred';
}
