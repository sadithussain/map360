import { ChangeEvent, FormEvent, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { login, ApiError } from "../lib/api";
import { saveAuthToken } from "../lib/auth";

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function Login() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const redirectTo = searchParams.get("redirect") || "/groups";

  const [formData, setFormData] = useState({
    email: "",
    password: "",
  });

  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");

  const isFormValid =
    !submitting &&
    EMAIL_REGEX.test(formData.email) &&
    formData.password.length > 0;

  function handleChange(e: ChangeEvent<HTMLInputElement>) {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  }

  async function handleLogin(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!isFormValid) {
      return;
    }

    setSubmitError("");
    setSubmitting(true);
    try {
      const data = await login({
        email: formData.email,
        password: formData.password,
      });
      saveAuthToken(data.access_token, data.token_type);
      navigate(redirectTo);
    } catch (error) {
      if (error instanceof ApiError) {
        if (error.status === 401) {
          setSubmitError("Incorrect email or password.");
        } else {
          setSubmitError(error.message || "Login failed. Please try again.");
        }
      } else {
        console.error(`Failed to log in: ${error}`);
        setSubmitError("Unable to reach the server. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <section className="flex min-h-screen items-center justify-center bg-gray-100">
        <form
          onSubmit={handleLogin}
          noValidate
          className="w-full max-w-md rounded-xl bg-white p-8 shadow-lg"
        >
          <h1 className="mb-6 text-center text-3xl font-bold">Welcome Back</h1>

          <fieldset className="flex flex-col gap-4">
            <div className="flex flex-col gap-1">
              <label htmlFor="email" className="font-medium">
                Email Address
              </label>
              <input
                className="rounded-md border p-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                type="email"
                id="email"
                name="email"
                value={formData.email}
                autoComplete="email"
                onChange={handleChange}
                required
              />
            </div>

            <div className="flex flex-col gap-1">
              <label htmlFor="password" className="font-medium">
                Password
              </label>
              <input
                className="rounded-md border p-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                type="password"
                id="password"
                name="password"
                value={formData.password}
                autoComplete="current-password"
                onChange={handleChange}
                required
              />
            </div>

            {submitError && (
              <p className="text-sm text-red-600">{submitError}</p>
            )}

            <button
              type="submit"
              disabled={!isFormValid}
              className="mt-4 rounded-md bg-blue-600 py-2 text-white transition hover:bg-blue-700 hover:cursor-pointer disabled:cursor-not-allowed disabled:opacity-60"
            >
              {submitting ? "Logging In..." : "Log In"}
            </button>

            <p className="text-center text-sm text-gray-600">
              Don't have an account?{" "}
              <Link to="/register" className="text-blue-600 hover:underline">
                Create one
              </Link>
            </p>
          </fieldset>
        </form>
      </section>
    </div>
  );
}

export default Login;
