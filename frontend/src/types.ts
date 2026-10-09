export type ProjectRef = {
  slug: string;
  name: string;
};

export type Project = ProjectRef & {
  panels: string[];
};

export type PanelDef = {
  key: string;
  label: string;
  group: string;
  description: string;
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
  project: ProjectRef;
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
