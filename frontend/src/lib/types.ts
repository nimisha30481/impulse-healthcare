export type Role = "patient" | "doctor" | "caregiver" | "support" | "admin";

export interface User {
  id: string;
  email: string;
  phone?: string | null;
  role: Role;
  full_name: string;
  preferred_name?: string | null;
  avatar_color: string;
  email_verified: boolean;
  mfa_enabled: boolean;
  is_demo: boolean;
  preferences: Preferences;
  patient_id?: string;
  mrn?: string;
  speciality?: string;
  verification_status?: string;
}

export interface Preferences {
  language?: string;
  theme?: "light" | "dark" | "system";
  text_size?: "normal" | "large" | "x-large";
  reduced_motion?: boolean;
  high_contrast?: boolean;
  country?: string;
  state?: string;
  timezone?: string;
  date_format?: string;
  units?: string;
  notifications?: Record<string, { email?: boolean; sms?: boolean }>;
  data_sharing?: Record<string, boolean>;
}

export interface Person {
  id: string;
  name: string;
  role: Role;
  avatar_color: string;
  speciality?: string;
}

export type DoseStatus =
  | "upcoming" | "due" | "taken_reported" | "missed_reported" | "snoozed" | "skipped"
  | "unconfirmed" | "awaiting_confirmation" | "cancelled";

export interface Dose {
  id: string;
  item_id: string;
  scheduled_at: string;
  status: DoseStatus;
  snoozed_until?: string | null;
  responded_at?: string | null;
  medicine: string;
  generic_name: string;
  strength: string;
  dose: string;
  route: string;
  instructions?: string | null;
  version_no: number;
}

export interface Version {
  id: string;
  version_no: number;
  status: string;
  generic_name: string;
  brand_name?: string | null;
  strength: string;
  dosage_form: string;
  dose_amount: number;
  dose_unit: string;
  route: string;
  frequency_label: string;
  indication?: string | null;
  duration_days?: number | null;
  start_date: string;
  end_date?: string | null;
  quantity?: string | null;
  refills_allowed: number;
  refill_instructions?: string | null;
  food_instructions?: string | null;
  special_instructions?: string | null;
  missed_dose_guidance?: string | null;
  effective_from: string;
  change_reason?: string | null;
  created_at: string;
  author?: Person | null;
  is_prn: boolean;
  schedule?: { times_of_day: string[]; days_of_week?: number[] | null; interval_days: number; timezone: string } | null;
}

export interface MedItem {
  id: string;
  status: string;
  bucket: "current" | "upcoming" | "completed" | "discontinued";
  lock_version: number;
  prescription_id: string;
  source: string;
  prescriber?: Person | null;
  current: Version;
  pending_change?: Version | null;
  discontinue?: { effective: string; reason: string; instructions?: string; follow_up?: string } | null;
  hold_reason?: string | null;
  updated_at: string;
  versions?: Version[];
  education?: { available: boolean; content: Record<string, string>; source?: string; reviewed_at?: string };
  events?: { id: string; kind: string; reason?: string; note?: string; at: string; source: string }[];
  interaction?: Assessment | null;
  assessments?: Assessment[];
  external?: boolean;
}

export interface Assessment {
  id: string;
  status: string;
  created_at: string;
  orchestrator: string;
  knowledge_source?: string | null;
  checks_performed: string[];
  checks_unavailable: string[];
  drug_drug_state: "assessed" | "unavailable" | "failed";
  alerts: {
    id: string; kind: string; severity: string; medicines: string[]; explanation: string;
    consequences?: string; source: string; source_updated_at?: string; review_guidance?: string;
  }[];
  medications_considered: string[];
  reviewed_at?: string | null;
  review_decision?: string | null;
  review_note?: string | null;
  disclaimer: string;
  patient_message?: string;
}

export interface Adherence {
  window_days: number;
  scheduled: number;
  taken_reported: number;
  missed_reported: number;
  skipped: number;
  unconfirmed: number;
  pending: number;
  responses_received: number;
  response_coverage: number | null;
  reported_rate: number | null;
  trend: { date: string; taken_reported: number; missed_reported: number; skipped: number; unconfirmed: number; pending: number }[];
  method: string;
}

export interface Appointment {
  id: string;
  patient_id: string;
  patient_name?: string;
  doctor: Person;
  starts_at: string;
  ends_at: string;
  consultation_type: string;
  status: string;
  reason?: string | null;
  location?: { name: string; address: string } | null;
  history: { at: string; event: string }[];
  join_available: boolean;
  follow_up_id?: string | null;
}

export interface Instruction {
  id: string;
  kind: "instruction" | "follow_up";
  audience: string;
  title: string;
  description: string;
  priority: string;
  created_at: string;
  expires_on?: string | null;
  requires_ack: boolean;
  acknowledged_at?: string | null;
  delivery_status: string;
  due_date?: string | null;
  timeframe?: string | null;
  appointment_request: boolean;
  appointment_id?: string | null;
  status: string;
  author?: Person;
  patient_id: string;
  patient_name?: string;
}

export interface NotificationItem {
  id: string;
  category: string;
  priority: string;
  title: string;
  body: string;
  link?: string | null;
  channel: string;
  delivery_status: string;
  created_at: string;
  read_at?: string | null;
  acknowledged_at?: string | null;
  patient_id?: string | null;
  other_channels?: { channel: string; status: string }[];
}

export interface RecordItem {
  id: string;
  record_type: string;
  title: string;
  summary?: string | null;
  occurred_at: string;
  doctor?: Person | null;
  organization?: string | null;
  document_id?: string | null;
  medication_names: string[];
  data: Record<string, string>;
  provenance: string;
  status: string;
  amends_id?: string | null;
}
