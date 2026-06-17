import { ChangeEvent, FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

// Mirror the backend schema constraints in backend/app/schemas/user_schema.py.
// The backend remains the source of truth; these enable immediate feedback.
const USERNAME_MIN = 3;
const USERNAME_MAX = 50;
const PASSWORD_MIN = 8;
const PASSWORD_MAX = 100;
const EMAIL_MAX = 254;

const API_BASE_URL = "http://127.0.0.1:8000";

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function LengthHint({ length, max }: { length: number; max: number }) {
  const atMax = length >= max;

  return (
    <p
      className={`text-sm ${atMax ? "text-amber-600" : "text-gray-500"}`}
      aria-live="polite"
    >
      {length}/{max}
      {atMax ? " — Maximum length reached" : ""}
    </p>
  );
}

function Register() {
  const navigate = useNavigate();

  const [formData, setFormData] = useState({
    email: "",
    username: "",
    password: "",
    passwordConfirm: "",
  });

  const [errors, setErrors] = useState({
    email: "",
    username: "",
    password: "",
    passwordConfirm: "",
  });

  const [checkingAvailability, setCheckingAvailability] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");

  let isFormValid =
  !checkingAvailability &&
  !submitting &&
  Object.values(errors).every(error => error === "") &&
  Object.values(formData).every(value => value.trim() !== "");

  useEffect(() => {
    if(formData.email.length === 0 || !EMAIL_REGEX.test(formData.email)) {
      return;
    }
    let cancelled = false;
    const timer = setTimeout(async () => {
      const email = formData.email;
      setCheckingAvailability(true);
      const isAvailable = await checkEmailAvailability(email);
      setCheckingAvailability(false);
      if(!cancelled) {
        setErrors((prev) => ({ ...prev, email: isAvailable ? "" : "Email already exists" }));
      }
    }, 500);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [formData.email]);

  useEffect(() => {
    if(formData.username.length < USERNAME_MIN || formData.username.length > USERNAME_MAX) {
      return;
    }
    let cancelled = false;
    const timer = setTimeout(async () => {
      const username = formData.username;
      setCheckingAvailability(true);
      const isAvailable = await checkUsernameAvailability(username);
      setCheckingAvailability(false);
      if(!cancelled) {
        setErrors((prev) => ({ ...prev, username: isAvailable ? "" : "Username already exists" }));
      }
    }, 500);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [formData.username]);

  async function checkEmailAvailability(email: string): Promise<boolean> {
    try {
      const response = await fetch(`${API_BASE_URL}/users/exists/email/${encodeURIComponent(email)}`);
      if (!response.ok) {
        throw new Error(`Failed to check email availability: ${response.statusText}`);
      }
      const exists: boolean = await response.json();

      return !exists;
    } catch (error) {
      console.error(`Failed to check email availability: ${error}`);
      return true;
    }
  }

  async function checkUsernameAvailability(username: string): Promise<boolean> {
    try {
      const response = await fetch(`${API_BASE_URL}/users/exists/username/${encodeURIComponent(username)}`);
      if (!response.ok) {
        throw new Error(`Failed to check username availability: ${response.statusText}`);
      }
      const exists: boolean = await response.json();

      return !exists;
    } catch (error) {
      console.error(`Failed to check username availability: ${error}`);
      return true;
    }
  }

  function validateField(
    name: string,
    value: string,
    data: typeof formData = formData,
  ) {
    switch (name) {
      case "email":
        if (value.length > EMAIL_MAX) {
          setErrors((prev) => ({
            ...prev,
            email: `Email must be at most ${EMAIL_MAX} characters`,
          }));
        } else if (!EMAIL_REGEX.test(value)) {
          setErrors((prev) => ({ ...prev, email: "Invalid email address" }));
        } else {
          setErrors((prev) => ({ ...prev, email: "" }));
        }
        break;
      case "username":
        if (value.length < USERNAME_MIN) {
          setErrors((prev) => ({
            ...prev,
            username: "Username must be at least 3 characters",
          }));
        } else if (value.length > USERNAME_MAX) {
          setErrors((prev) => ({
            ...prev,
            username: "Username must be at most 50 characters",
          }));
        } else {
          setErrors((prev) => ({ ...prev, username: "" }));
        }
        break;
      case "password":
        if (value.length < PASSWORD_MIN) {
          setErrors((prev) => ({
            ...prev,
            password: "Password must be at least 8 characters",
          }));
        } else if (value.length > PASSWORD_MAX) {
          setErrors((prev) => ({
            ...prev,
            password: "Password must be at most 100 characters",
          }));
        } else {
          setErrors((prev) => ({ ...prev, password: "" }));
        }
        break;
      case "passwordConfirm":
        if (value !== data.password) {
          setErrors((prev) => ({
            ...prev,
            passwordConfirm: "Passwords do not match",
          }));
        } else {
          setErrors((prev) => ({ ...prev, passwordConfirm: "" }));
        }
        break;
      default:
        break;
    }
  }

  function handleChange(e: ChangeEvent<HTMLInputElement>) {
    const { name, value } = e.target;
    const updatedFormData = { ...formData, [name]: value };
    setFormData(updatedFormData);
    validateField(name, value, updatedFormData);

    if (name === "password") {
      validateField(
        "passwordConfirm",
        updatedFormData.passwordConfirm,
        updatedFormData,
      );
    }
  }

  async function handleRegister(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!isFormValid) {
      return;
    }

    setSubmitError("");
    setSubmitting(true);
    try {
      const response = await fetch(`${API_BASE_URL}/users/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: formData.email,
          username: formData.username,
          password: formData.password,
        }),
      });

      if (!response.ok) {
        if (response.status === 409) {
          setSubmitError("A user with this email or username already exists.");
        } else {
          setSubmitError("Registration failed. Please try again.");
        }
        return;
      }

      navigate("/login");
    } catch (error) {
      console.error(`Failed to register: ${error}`);
      setSubmitError("Unable to reach the server. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <section className="flex min-h-screen items-center justify-center bg-gray-100">
        <form
          onSubmit={handleRegister}
          noValidate
          className="w-full max-w-md rounded-xl bg-white p-8 shadow-lg"
        >
          <h1 className="mb-6 text-center text-3xl font-bold">
            Create an Account
          </h1>

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
                maxLength={EMAIL_MAX}
                onChange={handleChange}
                required
              />
              {errors.email && (
                <p className="text-sm text-red-600">{errors.email}</p>
              )}
              <LengthHint length={formData.email.length} max={EMAIL_MAX} />
            </div>

            <div className="flex flex-col gap-1">
              <label htmlFor="username" className="font-medium">
                Username
              </label>
              <input
                className="rounded-md border p-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                type="text"
                id="username"
                name="username"
                value={formData.username}
                autoComplete="username"
                minLength={USERNAME_MIN}
                maxLength={USERNAME_MAX}
                onChange={handleChange}
                required
              />
              {errors.username && (
                <p className="text-sm text-red-600">{errors.username}</p>
              )}
              <LengthHint length={formData.username.length} max={USERNAME_MAX} />
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
                autoComplete="new-password"
                minLength={PASSWORD_MIN}
                maxLength={PASSWORD_MAX}
                onChange={handleChange}
                required
              />
              {errors.password && (
                <p className="text-sm text-red-600">{errors.password}</p>
              )}
              <LengthHint length={formData.password.length} max={PASSWORD_MAX} />
            </div>

            <div className="flex flex-col gap-1">
              <label htmlFor="password-confirm" className="font-medium">
                Confirm Password
              </label>
              <input
                className="rounded-md border p-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                type="password"
                id="password-confirm"
                name="passwordConfirm"
                value={formData.passwordConfirm}
                autoComplete="new-password"
                onChange={handleChange}
                required
              />
              {errors.passwordConfirm && (
                <p className="text-sm text-red-600">{errors.passwordConfirm}</p>
              )}
            </div>

            {submitError && (
              <p className="text-sm text-red-600">{submitError}</p>
            )}

            <button
              type="submit"
              disabled={!isFormValid}
              className="mt-4 rounded-md bg-blue-600 py-2 text-white transition hover:bg-blue-700 hover:cursor-pointer disabled:cursor-not-allowed disabled:opacity-60"
            >
              {submitting ? "Creating Account..." : "Create Account"}
            </button>
          </fieldset>
        </form>
      </section>
    </div>
  );
}

export default Register;
