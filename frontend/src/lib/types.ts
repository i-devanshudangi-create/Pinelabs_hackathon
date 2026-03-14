export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  toolCalls?: ToolCall[];
}

export interface ToolCall {
  tool_name: string;
  tool_input: Record<string, any>;
  tool_result?: Record<string, any>;
  timestamp: string;
}

export interface ActivityEntry {
  event: string;
  tool_name: string;
  tool_input?: Record<string, any>;
  tool_result?: Record<string, any>;
  timestamp: string;
}

export interface DashboardStats {
  totalOrders: number;
  totalPayments: number;
  totalRefunds: number;
  totalAmount: number;
}

export interface Decision {
  title: string;
  reasoning: string;
  options_considered: { option: string; verdict: string }[];
  chosen: string;
  confidence: 'high' | 'medium' | 'low';
}

export interface WorkflowStep {
  workflow_id: string;
  step_index: number;
  total_steps: number;
  step_name: string;
  status: 'pending' | 'running' | 'success' | 'failed';
  tool_name?: string;
  workflow_type?: string;
}

export interface ProactiveAlert {
  severity: 'info' | 'warning' | 'danger';
  title: string;
  message: string;
  suggested_action?: string;
}
