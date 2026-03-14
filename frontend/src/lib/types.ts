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
