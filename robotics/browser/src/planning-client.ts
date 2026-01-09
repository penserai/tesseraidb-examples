/**
 * Planning API client for browser-based PDDL planning.
 * Communicates with the TesseraiDB planning API.
 */

export interface PlanAction {
  name: string;
  parameters: string[];
}

export interface Plan {
  id: string;
  valid: boolean;
  actions: PlanAction[];
  stats: {
    planning_time_ms: number;
    states_explored: number;
    planner: string;
  };
}

export interface PlanningClientConfig {
  baseUrl: string;
  token?: string;
  timeout?: number;
}

export class PlanningClient {
  private baseUrl: string;
  private token: string;
  private timeout: number;

  constructor(config: PlanningClientConfig) {
    this.baseUrl = config.baseUrl.replace(/\/$/, "");
    this.token = config.token || "browser-client";
    this.timeout = config.timeout || 5000;
  }

  /**
   * Generate a plan from a PDDL problem.
   */
  async plan(domainId: string, problemPddl: string): Promise<Plan> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    try {
      const response = await fetch(`${this.baseUrl}/api/v1/planning/plan`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${this.token}`,
        },
        body: JSON.stringify({
          domain_id: domainId,
          problem_pddl: problemPddl,
          timeout_ms: this.timeout - 500, // Leave margin for network
        }),
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        const error = await response.text();
        throw new Error(`Planning API error: ${response.status} - ${error}`);
      }

      return await response.json();
    } catch (error) {
      clearTimeout(timeoutId);
      if (error instanceof Error && error.name === "AbortError") {
        throw new Error("Planning request timed out");
      }
      throw error;
    }
  }

  /**
   * Create a PDDL domain on the server.
   */
  async createDomain(id: string, name: string, pddl: string): Promise<void> {
    const response = await fetch(`${this.baseUrl}/api/v1/planning/domains`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${this.token}`,
      },
      body: JSON.stringify({ id, name, pddl }),
    });

    if (!response.ok && response.status !== 409) {
      // 409 = already exists, which is fine
      const error = await response.text();
      throw new Error(`Failed to create domain: ${response.status} - ${error}`);
    }
  }

  /**
   * Check if the planning API is available.
   */
  async healthCheck(): Promise<boolean> {
    try {
      const response = await fetch(`${this.baseUrl}/health`, {
        method: "GET",
        headers: {
          Authorization: `Bearer ${this.token}`,
        },
      });
      return response.ok;
    } catch {
      return false;
    }
  }
}
