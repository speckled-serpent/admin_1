export type Project = {
  slug: string;
  name: string;
};

export type Charge = {
  id: string;
  amount: number;
  amount_refunded: number;
  currency: string;
  status: string;
  refunded: boolean;
  created: number;
  description: string | null;
  customer: string | null;
};

export type Revenue = {
  project: Project;
  currency: string | null;
  gross_amount: number;
  refunded_amount: number;
  net_amount: number;
  charge_count: number;
  succeeded_count: number;
  refunded_count: number;
  charges: Charge[];
};

export type LoginResult = {
  token: string;
  token_type: string;
  expires_at: string;
  username: string;
};
