import { lazy, Suspense, useEffect, type ReactNode } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { MotionConfig } from "framer-motion";
import { PublicLayout } from "./components/layout/PublicLayout";
import { AppShell } from "./components/layout/AppShell";
import { Spinner } from "./components/ui/primitives";
import { applyPreferences, homeFor, useAuth } from "./lib/auth";
import { I18nProvider } from "./lib/i18n";
import type { Role } from "./lib/types";
import Landing from "./pages/public/Landing";

const p = (f: () => Promise<any>) => lazy(f);
const About = p(() => import("./pages/public/About"));
const Blueprint = p(() => import("./pages/public/Blueprint"));
const InfoPage = p(() => import("./pages/public/InfoPage"));
const Login = p(() => import("./pages/auth/Login"));
const Register = p(() => import("./pages/auth/Register"));
const VerifyEmail = p(() => import("./pages/auth/VerifyEmail"));
const ForgotPassword = p(() => import("./pages/auth/ForgotPassword"));
const ResetPassword = p(() => import("./pages/auth/ResetPassword"));
const MfaChallenge = p(() => import("./pages/auth/MfaChallenge"));
const PatientDashboard = p(() => import("./pages/patient/Dashboard"));
const Medicines = p(() => import("./pages/patient/Medicines"));
const MedicineDetail = p(() => import("./pages/patient/MedicineDetail"));
const Records = p(() => import("./pages/patient/Records"));
const PatientAppointments = p(() => import("./pages/patient/Appointments"));
const CareTeam = p(() => import("./pages/patient/CareTeam"));
const Reports = p(() => import("./pages/patient/Reports"));
const DoctorDashboard = p(() => import("./pages/doctor/Dashboard"));
const DoctorPatients = p(() => import("./pages/doctor/Patients"));
const DoctorPatient = p(() => import("./pages/doctor/PatientProfile"));
const DoctorAppointments = p(() => import("./pages/doctor/Appointments"));
const DoctorPrescriptions = p(() => import("./pages/doctor/Prescriptions"));
const AdherenceAlerts = p(() => import("./pages/doctor/AdherenceAlerts"));
const Briefs = p(() => import("./pages/doctor/Briefs"));
const FollowUps = p(() => import("./pages/doctor/FollowUps"));
const Verification = p(() => import("./pages/doctor/Verification"));
const CaregiverDashboard = p(() => import("./pages/caregiver/Dashboard"));
const CaregiverPatient = p(() => import("./pages/caregiver/PatientView"));
const CaregiverAccept = p(() => import("./pages/caregiver/Accept"));
const SupportCases = p(() => import("./pages/support/Cases"));
const SupportCase = p(() => import("./pages/support/CaseDetail"));
const AdminHome = p(() => import("./pages/admin/AdminHome"));
const AuditLog = p(() => import("./pages/admin/AuditLog"));
const Notifications = p(() => import("./pages/shared/Notifications"));
const Settings = p(() => import("./pages/shared/Settings"));
const Directory = p(() => import("./pages/shared/Directory"));
const Messages = p(() => import("./pages/shared/Messages"));
const Integrations = p(() => import("./pages/shared/Integrations"));
const HelpCenter = p(() => import("./pages/shared/HelpCenter"));

function Loading() {
  return <div className="grid min-h-[40vh] place-items-center"><Spinner /></div>;
}

function RequireAuth({ roles, children }: { roles?: Role[]; children: ReactNode }) {
  const { user, session, loading } = useAuth();
  const loc = useLocation();
  if (loading) return <Loading />;
  if (session?.mfa_pending) return <Navigate to="/mfa" replace />;
  if (!user) return <Navigate to={`/login?next=${encodeURIComponent(loc.pathname + loc.search)}`} replace />;
  if (roles && !roles.includes(user.role)) return <Navigate to={homeFor(user.role)} replace />;
  return <>{children}</>;
}

export default function App() {
  const { user } = useAuth();
  const prefs = user?.preferences;
  useEffect(() => applyPreferences(prefs), [prefs]);
  useEffect(() => {
    const mq = window.matchMedia?.("(prefers-color-scheme: dark)");
    const on = () => applyPreferences(prefs);
    mq?.addEventListener?.("change", on);
    return () => mq?.removeEventListener?.("change", on);
  }, [prefs]);

  return (
    <I18nProvider lang={prefs?.language ?? "en"}>
      <MotionConfig reducedMotion={prefs?.reduced_motion ? "always" : "user"}>
        <Suspense fallback={<Loading />}>
          <Routes>
            <Route element={<PublicLayout />}>
              <Route index element={<Landing />} />
              <Route path="about" element={<About />} />
              <Route path="blueprint" element={<Blueprint />} />
              {["privacy", "terms", "security", "accessibility", "contact", "help"].map((slug) => (
                <Route key={slug} path={slug} element={<InfoPage slug={slug} />} />
              ))}
              <Route path="login" element={<Login />} />
              <Route path="register" element={<Register />} />
              <Route path="verify-email" element={<VerifyEmail />} />
              <Route path="forgot-password" element={<ForgotPassword />} />
              <Route path="reset-password" element={<ResetPassword />} />
              <Route path="mfa" element={<MfaChallenge />} />
              <Route path="caregiver/accept" element={<CaregiverAccept />} />
            </Route>

            <Route element={<RequireAuth><AppShell /></RequireAuth>}>
              <Route path="app" element={<Navigate to={user ? homeFor(user.role) : "/login"} replace />} />
              <Route path="patient" element={<RequireAuth roles={["patient"]}><PatientDashboard /></RequireAuth>} />
              <Route path="patient/medicines" element={<RequireAuth roles={["patient"]}><Medicines /></RequireAuth>} />
              <Route path="patient/medicines/:itemId" element={<RequireAuth roles={["patient"]}><MedicineDetail /></RequireAuth>} />
              <Route path="patient/records" element={<RequireAuth roles={["patient"]}><Records /></RequireAuth>} />
              <Route path="patient/appointments" element={<RequireAuth roles={["patient"]}><PatientAppointments /></RequireAuth>} />
              <Route path="patient/care-team" element={<RequireAuth roles={["patient"]}><CareTeam /></RequireAuth>} />
              <Route path="patient/reports" element={<RequireAuth roles={["patient"]}><Reports /></RequireAuth>} />

              <Route path="doctor" element={<RequireAuth roles={["doctor"]}><DoctorDashboard /></RequireAuth>} />
              <Route path="doctor/patients" element={<RequireAuth roles={["doctor"]}><DoctorPatients /></RequireAuth>} />
              <Route path="doctor/patients/:patientId" element={<RequireAuth roles={["doctor"]}><DoctorPatient /></RequireAuth>} />
              <Route path="doctor/appointments" element={<RequireAuth roles={["doctor"]}><DoctorAppointments /></RequireAuth>} />
              <Route path="doctor/prescriptions" element={<RequireAuth roles={["doctor"]}><DoctorPrescriptions /></RequireAuth>} />
              <Route path="doctor/adherence" element={<RequireAuth roles={["doctor"]}><AdherenceAlerts /></RequireAuth>} />
              <Route path="doctor/briefs" element={<RequireAuth roles={["doctor"]}><Briefs /></RequireAuth>} />
              <Route path="doctor/briefs/:briefId" element={<RequireAuth roles={["doctor"]}><Briefs /></RequireAuth>} />
              <Route path="doctor/follow-ups" element={<RequireAuth roles={["doctor"]}><FollowUps /></RequireAuth>} />
              <Route path="doctor/verification" element={<RequireAuth roles={["doctor"]}><Verification /></RequireAuth>} />

              <Route path="caregiver" element={<RequireAuth roles={["caregiver"]}><CaregiverDashboard /></RequireAuth>} />
              <Route path="caregiver/patients/:patientId" element={<RequireAuth roles={["caregiver"]}><CaregiverPatient /></RequireAuth>} />

              <Route path="support" element={<RequireAuth roles={["support"]}><SupportCases /></RequireAuth>} />
              <Route path="support/cases/:caseId" element={<RequireAuth roles={["support"]}><SupportCase /></RequireAuth>} />

              <Route path="admin" element={<RequireAuth roles={["admin"]}><AdminHome /></RequireAuth>} />
              <Route path="admin/audit" element={<RequireAuth roles={["admin"]}><AuditLog /></RequireAuth>} />

              <Route path="notifications" element={<Notifications />} />
              <Route path="settings" element={<Settings />} />
              <Route path="messages" element={<Messages />} />
              <Route path="integrations" element={<Integrations />} />
              <Route path="support-help" element={<HelpCenter />} />
              <Route path="find-care" element={<Directory />} />
            </Route>
            <Route element={<PublicLayout />}>
              <Route path="directory" element={user ? <Navigate to="/find-care" replace /> : <Directory />} />
              <Route path="*" element={<InfoPage slug="404" />} />
            </Route>
          </Routes>
        </Suspense>
      </MotionConfig>
    </I18nProvider>
  );
}
