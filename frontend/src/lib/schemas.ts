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

export const deliverableSchema = z.object({
  code: z.string().max(50).optional().or(z.literal("")),
  title: z.string().min(1, "informe o título").max(300),
  description: z.string().optional().or(z.literal("")),
  phase: z.string().max(100).optional().or(z.literal("")),
  category: z.string().max(100).optional().or(z.literal("")),
  complexity: z.enum(["low", "medium", "high"]).optional(),
  source_excerpt: z.string().optional().or(z.literal("")),
  due_date: z.string().optional().or(z.literal("")),
});
export type DeliverableInput = z.infer<typeof deliverableSchema>;
