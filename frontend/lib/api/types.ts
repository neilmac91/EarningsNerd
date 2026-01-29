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
 */
export function getErrorStatus(error: unknown): number | undefined {
  if (isApiError(error)) {
    return error.response?.status;
  }
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
