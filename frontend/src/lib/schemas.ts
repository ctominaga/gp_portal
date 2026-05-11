import { z } from "zod";

export const loginSchema = z.object({
  email: z.string().email("e-mail inválido"),
  password: z.string().min(1, "informe a senha"),
});
export type LoginInput = z.infer<typeof loginSchema>;

export const projectCreateSchema = z.object({
  name: z.string().min(2, "mínimo 2 caracteres").max(200),
  client_name: z.string().min(2, "mínimo 2 caracteres").max(200),
  description: z.string().max(2000).optional().or(z.literal("")),
  started_at: z.string().optional().or(z.literal("")),
  client_user_email: z.string().email("e-mail inválido").optional().or(z.literal("")),
});
export type ProjectCreateInput = z.infer<typeof projectCreateSchema>;

export const reportCreateSchema = z
  .object({
    period_start: z.string().min(1, "informe a data inicial"),
    period_end: z.string().min(1, "informe a data final"),
  })
  .refine((d) => d.period_start <= d.period_end, {
    message: "início deve ser anterior ao fim",
    path: ["period_end"],
  });
export type ReportCreateInput = z.infer<typeof reportCreateSchema>;

// Enums alinhados ao prompt v1 e ao backend após F5.1 Deliverable.
export const DELIVERABLE_COMPLEXITY_VALUES = [
  "baixa", "baixa-media", "media", "media-alta", "alta",
] as const;
export const DELIVERABLE_CATEGORY_VALUES = [
  "tecnico", "tecnico-regulatorio", "negocio", "transversal", "governanca",
] as const;
export const DELIVERABLE_TYPE_VALUES = [
  "code_migration", "documentation", "knowledge_transfer", "stabilization",
  "deliverable_software", "assessment", "model", "infrastructure", "other",
] as const;
export const DELIVERABLE_STATUS_VALUES = [
  "not_started", "in_progress", "concluded", "blocked",
] as const;

export const deliverableSchema = z.object({
  code: z.string().max(50).optional().or(z.literal("")),
  title: z.string().min(1, "informe o título").max(300),
  description: z.string().optional().or(z.literal("")),
  phase: z.string().max(100).optional().or(z.literal("")),
  category: z.enum(DELIVERABLE_CATEGORY_VALUES).optional(),
  complexity: z.enum(DELIVERABLE_COMPLEXITY_VALUES).optional(),
  type: z.enum(DELIVERABLE_TYPE_VALUES).optional(),
  source_excerpt: z.string().optional().or(z.literal("")),
  due_date: z.string().optional().or(z.literal("")),
  acceptance_criteria: z.string().optional().or(z.literal("")),
  dependencies: z.array(z.string()).optional(),
  status: z.enum(DELIVERABLE_STATUS_VALUES).optional(),
});
export type DeliverableInput = z.infer<typeof deliverableSchema>;
