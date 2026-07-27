const { describe, it, expect } = require('@jest/globals');
const { Agent } = require('../agent/core');

describe('Gap 1: Core Agent Functionality', () => {
  it('should initialize an agent with configuration', () => {
    const agent = new Agent({ model: 'test' });
    expect(agent).toBeDefined();
    expect(agent.config).toEqual({ model: 'test' });
    expect(agent.status).toBe('initialized');
  });

  it('should execute a task and return a result', async () => {
    const agent = new Agent({ model: 'test' });
    const result = await agent.execute('test');
    expect(result).toBeDefined();
    expect(result.success).toBe(true);
    expect(result.message).toBeDefined();
    expect(result.data).toBeDefined();
  });

  it('should handle empty task gracefully', async () => {
    const agent = new Agent({ model: 'test' });
    const result = await agent.execute('');
    expect(result).toBeDefined();
    expect(result.success).toBe(false);
    expect(result.error).toBe('Empty task');
  });
});