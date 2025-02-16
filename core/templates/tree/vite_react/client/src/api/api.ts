import axios, { AxiosRequestConfig, AxiosError } from 'axios';

{% if options.auth_type == "api_key" %}
const API_KEY = import.meta.env.VITE_API_KEY;
{% endif %}

const api = axios.create({
  headers: {
    'Content-Type': 'application/json',
  },
  validateStatus: (status) => {
    return status >= 200 && status < 300;
  },
});

let accessToken: string | null = null;

{% if options.auth %}
// Axios request interceptor: Attach access token and API key to headers
api.interceptors.request.use(
  (config: AxiosRequestConfig): AxiosRequestConfig => {
    // Check if the request is not for login or register

{% if options.auth_type == "api_key" %}
  const isAuthEndpoint = config.url?.includes('/login') || config.url?.includes('/register');

  if (!isAuthEndpoint) {
  // Add API key for non-auth endpoints
  if (config.headers && API_KEY) {
    config.headers['api_key'] = API_KEY;  // or whatever header name your API expects
  }

{% endif %}

      // Add authorization token if available
      if (!accessToken) {
        accessToken = localStorage.getItem('accessToken');
      }
      if (accessToken && config.headers) {
        config.headers.Authorization = `Bearer ${accessToken}`;
      }
    }

    return config;
  },
  (error: AxiosError): Promise<AxiosError> => Promise.reject(error)
);

// Axios response interceptor: Handle 401 errors
api.interceptors.response.use(
  (response) => response, // If the response is successful, return it
  async (error: AxiosError): Promise<any> => {
    const originalRequest = error.config as AxiosRequestConfig & { _retry?: boolean };

    // If the error is due to an expired access token
    if ([401, 403].includes(error.response?.status) && !originalRequest._retry) {
      originalRequest._retry = true; // Mark the request as retried

      try {
        // Attempt to refresh the token
        const { data } = await axios.post(`/api/auth/refresh`, {
          refreshToken: localStorage.getItem('refreshToken'),
        });
        accessToken = data.data.accessToken;
        localStorage.setItem('accessToken', accessToken);
        localStorage.setItem('refreshToken', data.data.refreshToken);

        // Retry the original request with the new token
        if (originalRequest.headers) {
          originalRequest.headers.Authorization = `Bearer ${accessToken}`;
          // Ensure API key is still present in retry

{% if options.auth_type == "api_key" %}
          if (API_KEY) {
            originalRequest.headers['api_key'] = API_KEY;
          }
{% endif %}

        }
        return api(originalRequest);
      } catch (err) {
        // If refresh fails, clear tokens and redirect to login
        localStorage.removeItem('refreshToken');
        localStorage.removeItem('accessToken');
        accessToken = null;
        window.location.href = '/login'; // Redirect to login page
        return Promise.reject(err);
      }
    }

    return Promise.reject(error); // Pass other errors through
  }
);
{% endif %}

export default api;
