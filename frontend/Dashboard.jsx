import React, { useState, useEffect, useMemo } from 'react';
import { Shield, AlertTriangle, CheckCircle, XCircle, Clock, Users, Activity, Server, Link2, RefreshCw, Eye, ChevronRight, Bell, Zap, TrendingUp, Lock, Unlock, BarChart3, Network, Key, ArrowUp, ArrowDown, Scan, FileWarning, ShieldCheck, Play } from 'lucide-react';

// API Configuration
const API_BASE = 'http://localhost:8000';

// API Helper
const api = {
  headers: () => ({
    'Content-Type': 'application/json',
    'X-API-Key': localStorage.getItem('api_key') || ''
  }),
  
  async get(endpoint) {
    const res = await fetch(`${API_BASE}${endpoint}`, { headers: this.headers() });
    if (!res.ok) throw new Error(`API Error: ${res.status}`);
    return res.json();
  },
  
  async post(endpoint, data) {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      method: 'POST',
      headers: this.headers(),
      body: JSON.stringify(data)
    });
    if (!res.ok) throw new Error(`API Error: ${res.status}`);
    return res.json();
  }
};

// Severity colors
const severityColors = {
  critical: 'bg-red-500',
  high: 'bg-orange-500',
  medium: 'bg-yellow-500',
  low: 'bg-blue-500'
};

const priorityColors = {
  urgent: 'bg-red-500',
  high: 'bg-orange-500',
  normal: 'bg-blue-500',
  low: 'bg-gray-500'
};

// Login Screen
function LoginScreen({ onLogin }) {
  const [apiKey, setApiKey] = useState('');
  const [error, setError] = useState('');
  
  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      localStorage.setItem('api_key', apiKey);
      await api.get('/v1/system/status');
      onLogin();
    } catch (err) {
      setError('Invalid API key');
      localStorage.removeItem('api_key');
    }
  };
  
  return (
    <div className="min-h-screen bg-gray-900 flex items-center justify-center">
      <div className="bg-gray-800 p-8 rounded-lg shadow-xl w-96">
        <div className="flex items-center gap-3 mb-6">
          <Shield className="w-8 h-8 text-cyan-400" />
          <h1 className="text-2xl font-bold text-white">AI_NAS_OS</h1>
        </div>
        <p className="text-gray-400 mb-6">Zero-Trust Agent Platform</p>
        
        <form onSubmit={handleSubmit}>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="Enter API Key"
            className="w-full p-3 bg-gray-700 border border-gray-600 rounded text-white mb-4 focus:border-cyan-400 focus:outline-none"
          />
          {error && <p className="text-red-400 text-sm mb-4">{error}</p>}
          <button
            type="submit"
            className="w-full bg-cyan-600 hover:bg-cyan-500 text-white py-3 rounded font-medium transition"
          >
            Connect
          </button>
        </form>
        
        <p className="text-gray-500 text-xs mt-6 text-center">
          Quietfire AI • Bellevue, Ohio
        </p>
      </div>
    </div>
  );
}

// Status Card Component
function StatusCard({ title, value, icon: Icon, color, subtitle }) {
  return (
    <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-gray-400 text-sm">{title}</p>
          <p className={`text-2xl font-bold ${color || 'text-white'}`}>{value}</p>
          {subtitle && <p className="text-gray-500 text-xs mt-1">{subtitle}</p>}
        </div>
        <Icon className={`w-8 h-8 ${color || 'text-gray-600'}`} />
      </div>
    </div>
  );
}

// Approval Card Component
function ApprovalCard({ request, onApprove, onReject }) {
  const [deciding, setDeciding] = useState(false);
  const [notes, setNotes] = useState('');
  
  const handleDecision = async (approved) => {
    setDeciding(true);
    try {
      const endpoint = `/v1/approvals/${request.request_id}/${approved ? 'approve' : 'reject'}`;
      await api.post(endpoint, { decided_by: 'dashboard_user', notes });
      approved ? onApprove(request.request_id) : onReject(request.request_id);
    } catch (err) {
      console.error(err);
    }
    setDeciding(false);
  };
  
  const priorityColor = priorityColors[request.priority] || 'bg-gray-500';
  
  return (
    <div className="bg-gray-800 rounded-lg p-4 border border-gray-700 mb-3">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className={`px-2 py-0.5 rounded text-xs text-white ${priorityColor}`}>
            {request.priority}
          </span>
          <span className="text-gray-400 text-xs">{request.request_id}</span>
        </div>
        <span className="text-gray-500 text-xs">
          {new Date(request.created_at).toLocaleString()}
        </span>
      </div>
      
      <p className="text-white font-medium mb-1">{request.action}</p>
      <p className="text-gray-400 text-sm mb-3">{request.description}</p>
      
      <div className="bg-gray-900 rounded p-2 mb-3">
        <p className="text-gray-500 text-xs mb-1">Agent: <span className="text-cyan-400">{request.agent_id}</span></p>
        <p className="text-gray-500 text-xs">Payload: <code className="text-gray-400">{JSON.stringify(request.payload).slice(0, 100)}</code></p>
      </div>
      
      <input
        type="text"
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        placeholder="Decision notes (optional)"
        className="w-full p-2 bg-gray-700 border border-gray-600 rounded text-white text-sm mb-3 focus:border-cyan-400 focus:outline-none"
      />
      
      <div className="flex gap-2">
        <button
          onClick={() => handleDecision(true)}
          disabled={deciding}
          className="flex-1 bg-green-600 hover:bg-green-500 disabled:bg-gray-600 text-white py-2 rounded text-sm font-medium transition flex items-center justify-center gap-2"
        >
          <CheckCircle className="w-4 h-4" /> Approve
        </button>
        <button
          onClick={() => handleDecision(false)}
          disabled={deciding}
          className="flex-1 bg-red-600 hover:bg-red-500 disabled:bg-gray-600 text-white py-2 rounded text-sm font-medium transition flex items-center justify-center gap-2"
        >
          <XCircle className="w-4 h-4" /> Reject
        </button>
      </div>
    </div>
  );
}

// Anomaly Card Component
function AnomalyCard({ anomaly, onResolve }) {
  const [resolving, setResolving] = useState(false);
  const [notes, setNotes] = useState('');
  const [expanded, setExpanded] = useState(false);
  
  const handleResolve = async () => {
    if (!notes.trim()) return;
    setResolving(true);
    try {
      await api.post(`/v1/anomalies/${anomaly.anomaly_id}/resolve`, { resolution_notes: notes });
      onResolve(anomaly.anomaly_id);
    } catch (err) {
      console.error(err);
    }
    setResolving(false);
  };
  
  const severityColor = severityColors[anomaly.severity] || 'bg-gray-500';
  
  return (
    <div className="bg-gray-800 rounded-lg p-4 border border-gray-700 mb-3">
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className={`px-2 py-0.5 rounded text-xs text-white ${severityColor}`}>
            {anomaly.severity}
          </span>
          <span className="text-gray-400 text-xs">{anomaly.anomaly_type}</span>
        </div>
        {anomaly.requires_human_review && (
          <span className="flex items-center gap-1 text-yellow-400 text-xs">
            <Eye className="w-3 h-3" /> Review Required
          </span>
        )}
      </div>
      
      <p className="text-white mb-1">Agent: <span className="text-cyan-400">{anomaly.agent_id}</span></p>
      <p className="text-gray-400 text-sm mb-2">{anomaly.description}</p>
      
      <button 
        onClick={() => setExpanded(!expanded)}
        className="text-gray-500 text-xs flex items-center gap-1 mb-3 hover:text-gray-300"
      >
        <ChevronRight className={`w-3 h-3 transition ${expanded ? 'rotate-90' : ''}`} />
        {expanded ? 'Hide' : 'Show'} evidence
      </button>
      
      {expanded && (
        <div className="bg-gray-900 rounded p-2 mb-3 text-xs">
          <pre className="text-gray-400 overflow-x-auto">{JSON.stringify(anomaly.evidence, null, 2)}</pre>
        </div>
      )}
      
      <div className="flex gap-2">
        <input
          type="text"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Resolution notes..."
          className="flex-1 p-2 bg-gray-700 border border-gray-600 rounded text-white text-sm focus:border-cyan-400 focus:outline-none"
        />
        <button
          onClick={handleResolve}
          disabled={resolving || !notes.trim()}
          className="bg-cyan-600 hover:bg-cyan-500 disabled:bg-gray-600 text-white px-4 py-2 rounded text-sm font-medium transition"
        >
          Resolve
        </button>
      </div>
    </div>
  );
}

// Agent Card Component
function AgentCard({ agent }) {
  const [expanded, setExpanded] = useState(false);
  
  return (
    <div className="bg-gray-800 rounded-lg p-4 border border-gray-700 mb-3">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Zap className="w-4 h-4 text-cyan-400" />
          <span className="text-white font-medium">{agent.agent_id}</span>
        </div>
        <span className={`w-2 h-2 rounded-full ${agent.signing_key_registered ? 'bg-green-400' : 'bg-red-400'}`} />
      </div>
      
      <p className="text-gray-500 text-sm mb-2">
        {agent.capabilities?.length || 0} capabilities registered
      </p>
      
      <button 
        onClick={() => setExpanded(!expanded)}
        className="text-gray-500 text-xs flex items-center gap-1 hover:text-gray-300"
      >
        <ChevronRight className={`w-3 h-3 transition ${expanded ? 'rotate-90' : ''}`} />
        {expanded ? 'Hide' : 'Show'} capabilities
      </button>
      
      {expanded && agent.capabilities && (
        <div className="mt-2 space-y-1">
          {agent.capabilities.map((cap, i) => (
            <div key={i} className="bg-gray-900 rounded px-2 py-1">
              <code className="text-cyan-400 text-xs">{cap}</code>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// Federation Relationship Card
function FederationCard({ relationship }) {
  const statusColors = {
    established: 'text-green-400',
    pending_inbound: 'text-yellow-400',
    pending_outbound: 'text-yellow-400',
    revoked: 'text-red-400'
  };

  return (
    <div className="bg-gray-800 rounded-lg p-4 border border-gray-700 mb-3">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Link2 className="w-4 h-4 text-purple-400" />
          <span className="text-white font-medium">
            {relationship.remote_organization || relationship.remote_instance}
          </span>
        </div>
        <span className={`text-xs ${statusColors[relationship.status] || 'text-gray-400'}`}>
          {relationship.status}
        </span>
      </div>

      <p className="text-gray-500 text-xs mb-1">
        Instance: <span className="text-gray-400">{relationship.remote_instance}</span>
      </p>
      <p className="text-gray-500 text-xs mb-1">
        Trust Level: <span className="text-gray-400">{relationship.trust_level}</span>
      </p>
      {relationship.remote_fingerprint && (
        <p className="text-gray-500 text-xs">
          Fingerprint: <code className="text-gray-400">{relationship.remote_fingerprint}</code>
        </p>
      )}

      {relationship.status === 'established' && (
        <div className="mt-2 pt-2 border-t border-gray-700 flex gap-4 text-xs">
          <span className="text-gray-500">
            Sent: <span className="text-cyan-400">{relationship.messages_sent || 0}</span>
          </span>
          <span className="text-gray-500">
            Received: <span className="text-cyan-400">{relationship.messages_received || 0}</span>
          </span>
        </div>
      )}
    </div>
  );
}

// Trust Level Badge Component
const trustLevelColors = {
  quarantine: { bg: 'bg-red-900', text: 'text-red-400', border: 'border-red-700' },
  probation: { bg: 'bg-yellow-900', text: 'text-yellow-400', border: 'border-yellow-700' },
  resident: { bg: 'bg-blue-900', text: 'text-blue-400', border: 'border-blue-700' },
  citizen: { bg: 'bg-green-900', text: 'text-green-400', border: 'border-green-700' }
};

function TrustLevelBadge({ level }) {
  const colors = trustLevelColors[level] || trustLevelColors.quarantine;
  const icons = {
    quarantine: Lock,
    probation: Eye,
    resident: Users,
    citizen: Shield
  };
  const Icon = icons[level] || Lock;

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs ${colors.bg} ${colors.text} border ${colors.border}`}>
      <Icon className="w-3 h-3" />
      {level}
    </span>
  );
}

// Anomaly Heatmap Component (Agent × Time)
function AnomalyHeatmap({ anomalies, agents }) {
  const hours = useMemo(() => {
    const now = new Date();
    return Array.from({ length: 24 }, (_, i) => {
      const h = new Date(now);
      h.setHours(now.getHours() - 23 + i, 0, 0, 0);
      return h;
    });
  }, []);

  const heatmapData = useMemo(() => {
    const data = {};
    const agentIds = [...new Set([...agents.map(a => a.agent_id), ...anomalies.map(a => a.agent_id)])];

    agentIds.forEach(agentId => {
      data[agentId] = hours.map(hour => {
        const hourEnd = new Date(hour);
        hourEnd.setHours(hour.getHours() + 1);

        const count = anomalies.filter(a => {
          const aTime = new Date(a.detected_at);
          return a.agent_id === agentId && aTime >= hour && aTime < hourEnd;
        }).length;

        return count;
      });
    });

    return { agentIds, data };
  }, [anomalies, agents, hours]);

  const getHeatColor = (count) => {
    if (count === 0) return 'bg-gray-800';
    if (count === 1) return 'bg-yellow-900';
    if (count === 2) return 'bg-orange-800';
    if (count >= 3) return 'bg-red-700';
    return 'bg-gray-800';
  };

  if (heatmapData.agentIds.length === 0) {
    return (
      <div className="text-gray-500 text-sm text-center py-4">
        No agent activity to display
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <div className="min-w-[600px]">
        <div className="flex mb-2">
          <div className="w-24 flex-shrink-0" />
          <div className="flex-1 flex justify-between text-xs text-gray-500">
            <span>-24h</span>
            <span>-12h</span>
            <span>Now</span>
          </div>
        </div>

        {heatmapData.agentIds.slice(0, 8).map(agentId => (
          <div key={agentId} className="flex items-center mb-1">
            <div className="w-24 flex-shrink-0 text-xs text-gray-400 truncate pr-2" title={agentId}>
              {agentId.length > 12 ? agentId.slice(0, 12) + '...' : agentId}
            </div>
            <div className="flex-1 flex gap-0.5">
              {heatmapData.data[agentId].map((count, i) => (
                <div
                  key={i}
                  className={`flex-1 h-4 rounded-sm ${getHeatColor(count)} cursor-pointer hover:ring-1 hover:ring-white`}
                  title={`${agentId}: ${count} anomalies at ${hours[i].toLocaleTimeString()}`}
                />
              ))}
            </div>
          </div>
        ))}

        <div className="flex items-center gap-4 mt-4 text-xs text-gray-500">
          <span>Legend:</span>
          <span className="flex items-center gap-1"><div className="w-3 h-3 bg-gray-800 rounded-sm" /> 0</span>
          <span className="flex items-center gap-1"><div className="w-3 h-3 bg-yellow-900 rounded-sm" /> 1</span>
          <span className="flex items-center gap-1"><div className="w-3 h-3 bg-orange-800 rounded-sm" /> 2</span>
          <span className="flex items-center gap-1"><div className="w-3 h-3 bg-red-700 rounded-sm" /> 3+</span>
        </div>
      </div>
    </div>
  );
}

// Approval Queue with Wait Times
function ApprovalQueue({ approvals }) {
  const queueStats = useMemo(() => {
    const now = new Date();
    const byPriority = { urgent: [], high: [], normal: [], low: [] };

    approvals.forEach(a => {
      const created = new Date(a.created_at);
      const waitMinutes = Math.floor((now - created) / 60000);
      byPriority[a.priority]?.push({ ...a, waitMinutes });
    });

    const avgWait = approvals.length > 0
      ? Math.floor(approvals.reduce((sum, a) => sum + (now - new Date(a.created_at)) / 60000, 0) / approvals.length)
      : 0;

    return { byPriority, avgWait };
  }, [approvals]);

  const formatWait = (mins) => {
    if (mins < 60) return `${mins}m`;
    if (mins < 1440) return `${Math.floor(mins / 60)}h ${mins % 60}m`;
    return `${Math.floor(mins / 1440)}d`;
  };

  return (
    <div>
      <div className="grid grid-cols-4 gap-2 mb-4">
        {['urgent', 'high', 'normal', 'low'].map(priority => (
          <div key={priority} className={`rounded p-3 ${priority === 'urgent' ? 'bg-red-900/30' : 'bg-gray-900'}`}>
            <div className="flex items-center justify-between mb-1">
              <span className={`text-xs ${priorityColors[priority].replace('bg-', 'text-').replace('-500', '-400')}`}>
                {priority.charAt(0).toUpperCase() + priority.slice(1)}
              </span>
              <span className="text-white font-bold">{queueStats.byPriority[priority].length}</span>
            </div>
            {queueStats.byPriority[priority].length > 0 && (
              <span className="text-gray-500 text-xs">
                Oldest: {formatWait(Math.max(...queueStats.byPriority[priority].map(a => a.waitMinutes)))}
              </span>
            )}
          </div>
        ))}
      </div>

      <div className="flex items-center justify-between text-sm">
        <span className="text-gray-400">Average Wait Time:</span>
        <span className={`font-medium ${queueStats.avgWait > 60 ? 'text-orange-400' : 'text-green-400'}`}>
          {formatWait(queueStats.avgWait)}
        </span>
      </div>

      {queueStats.byPriority.urgent.length > 0 && (
        <div className="mt-3 p-2 bg-red-900/20 border border-red-700 rounded text-sm">
          <span className="text-red-400 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" />
            {queueStats.byPriority.urgent.length} urgent approval(s) waiting!
          </span>
        </div>
      )}
    </div>
  );
}

// Federation Trust Graph
function FederationTrustGraph({ relationships, instanceId }) {
  const graphData = useMemo(() => {
    const established = relationships.filter(r => r.status === 'established');
    const pending = relationships.filter(r => r.status.includes('pending'));
    const revoked = relationships.filter(r => r.status === 'revoked');

    return { established, pending, revoked };
  }, [relationships]);

  const trustLevelOrder = ['full', 'high', 'medium', 'limited', 'minimal'];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-center">
        <div className="bg-cyan-900/50 border-2 border-cyan-500 rounded-lg px-4 py-2">
          <div className="flex items-center gap-2">
            <Shield className="w-5 h-5 text-cyan-400" />
            <span className="text-cyan-400 font-medium">{instanceId || 'This Instance'}</span>
          </div>
        </div>
      </div>

      {graphData.established.length > 0 && (
        <div className="relative">
          <div className="absolute left-1/2 w-0.5 h-8 bg-green-600 -top-4" />
          <div className="flex flex-wrap justify-center gap-3 pt-4">
            {graphData.established.map((rel, i) => (
              <div key={i} className="relative">
                <div className="bg-gray-800 border border-green-600 rounded-lg px-3 py-2">
                  <p className="text-white text-sm font-medium">{rel.remote_organization || rel.remote_instance}</p>
                  <p className="text-gray-500 text-xs">Trust: {rel.trust_level}</p>
                  <div className="flex items-center gap-2 mt-1 text-xs">
                    <span className="text-green-400">↑{rel.messages_sent || 0}</span>
                    <span className="text-blue-400">↓{rel.messages_received || 0}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {graphData.pending.length > 0 && (
        <div className="flex flex-wrap justify-center gap-3 pt-4">
          {graphData.pending.map((rel, i) => (
            <div key={i} className="bg-gray-800 border border-yellow-600 border-dashed rounded-lg px-3 py-2">
              <p className="text-gray-400 text-sm">{rel.remote_instance}</p>
              <p className="text-yellow-500 text-xs">{rel.status.replace('_', ' ')}</p>
            </div>
          ))}
        </div>
      )}

      <div className="flex justify-center gap-6 text-xs text-gray-500 pt-4">
        <span className="flex items-center gap-1">
          <div className="w-3 h-3 border border-green-600 rounded" /> Established
        </span>
        <span className="flex items-center gap-1">
          <div className="w-3 h-3 border border-yellow-600 border-dashed rounded" /> Pending
        </span>
      </div>
    </div>
  );
}

// Capability Analytics Component
function CapabilityAnalytics({ agents }) {
  const analytics = useMemo(() => {
    const capCount = {};
    const resourceTypes = {};
    const actionTypes = {};

    agents.forEach(agent => {
      (agent.capabilities || []).forEach(cap => {
        capCount[cap] = (capCount[cap] || 0) + 1;

        const parts = cap.split(':');
        if (parts.length >= 2) {
          const resource = parts[0];
          const action = parts[1];
          resourceTypes[resource] = (resourceTypes[resource] || 0) + 1;
          actionTypes[action] = (actionTypes[action] || 0) + 1;
        }
      });
    });

    const totalCaps = Object.values(capCount).reduce((a, b) => a + b, 0);
    const uniqueCaps = Object.keys(capCount).length;
    const avgPerAgent = agents.length > 0 ? (totalCaps / agents.length).toFixed(1) : 0;

    const topResources = Object.entries(resourceTypes)
      .sort(([, a], [, b]) => b - a)
      .slice(0, 5);

    const topActions = Object.entries(actionTypes)
      .sort(([, a], [, b]) => b - a)
      .slice(0, 5);

    return { totalCaps, uniqueCaps, avgPerAgent, topResources, topActions };
  }, [agents]);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-gray-900 rounded p-3 text-center">
          <p className="text-2xl font-bold text-cyan-400">{analytics.uniqueCaps}</p>
          <p className="text-gray-500 text-xs">Unique Capabilities</p>
        </div>
        <div className="bg-gray-900 rounded p-3 text-center">
          <p className="text-2xl font-bold text-white">{analytics.totalCaps}</p>
          <p className="text-gray-500 text-xs">Total Grants</p>
        </div>
        <div className="bg-gray-900 rounded p-3 text-center">
          <p className="text-2xl font-bold text-purple-400">{analytics.avgPerAgent}</p>
          <p className="text-gray-500 text-xs">Avg per Agent</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <h4 className="text-gray-400 text-xs mb-2">Top Resources</h4>
          <div className="space-y-1">
            {analytics.topResources.map(([resource, count]) => (
              <div key={resource} className="flex items-center justify-between">
                <span className="text-gray-300 text-sm truncate">{resource}</span>
                <span className="text-cyan-400 text-sm">{count}</span>
              </div>
            ))}
          </div>
        </div>
        <div>
          <h4 className="text-gray-400 text-xs mb-2">Top Actions</h4>
          <div className="space-y-1">
            {analytics.topActions.map(([action, count]) => (
              <div key={action} className="flex items-center justify-between">
                <span className="text-gray-300 text-sm truncate">{action}</span>
                <span className="text-purple-400 text-sm">{count}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// Enhanced Agent Card with Trust Level
function EnhancedAgentCard({ agent, onPromote, onDemote }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="bg-gray-800 rounded-lg p-4 border border-gray-700 mb-3">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Zap className="w-4 h-4 text-cyan-400" />
          <span className="text-white font-medium">{agent.agent_id}</span>
        </div>
        <span className={`w-2 h-2 rounded-full ${agent.signing_key_registered ? 'bg-green-400' : 'bg-red-400'}`} />
      </div>

      <div className="flex items-center gap-2 mb-2">
        <TrustLevelBadge level={agent.trust_level || 'quarantine'} />
        {agent.trust_level !== 'citizen' && onPromote && (
          <button
            onClick={() => onPromote(agent.agent_id)}
            className="text-green-400 hover:text-green-300 p-1"
            title="Promote"
          >
            <ArrowUp className="w-3 h-3" />
          </button>
        )}
        {agent.trust_level !== 'quarantine' && onDemote && (
          <button
            onClick={() => onDemote(agent.agent_id)}
            className="text-red-400 hover:text-red-300 p-1"
            title="Demote"
          >
            <ArrowDown className="w-3 h-3" />
          </button>
        )}
      </div>

      {agent.behavioral_score !== undefined && (
        <div className="mb-2">
          <div className="flex items-center justify-between text-xs mb-1">
            <span className="text-gray-500">Behavioral Score</span>
            <span className={agent.behavioral_score >= 80 ? 'text-green-400' : agent.behavioral_score >= 50 ? 'text-yellow-400' : 'text-red-400'}>
              {agent.behavioral_score}%
            </span>
          </div>
          <div className="w-full h-1 bg-gray-700 rounded">
            <div
              className={`h-1 rounded ${agent.behavioral_score >= 80 ? 'bg-green-500' : agent.behavioral_score >= 50 ? 'bg-yellow-500' : 'bg-red-500'}`}
              style={{ width: `${agent.behavioral_score}%` }}
            />
          </div>
        </div>
      )}

      <p className="text-gray-500 text-sm mb-2">
        {agent.capabilities?.length || 0} capabilities registered
      </p>

      <button
        onClick={() => setExpanded(!expanded)}
        className="text-gray-500 text-xs flex items-center gap-1 hover:text-gray-300"
      >
        <ChevronRight className={`w-3 h-3 transition ${expanded ? 'rotate-90' : ''}`} />
        {expanded ? 'Hide' : 'Show'} capabilities
      </button>

      {expanded && agent.capabilities && (
        <div className="mt-2 space-y-1">
          {agent.capabilities.map((cap, i) => (
            <div key={i} className="bg-gray-900 rounded px-2 py-1">
              <code className="text-cyan-400 text-xs">{cap}</code>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// System-Wide Analysis Panel
function SystemAnalysisPanel() {
  const [analyzing, setAnalyzing] = useState(false);
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);
  const [autoRemediate, setAutoRemediate] = useState(false);
  const [showFindings, setShowFindings] = useState(false);

  const runAnalysis = async () => {
    setAnalyzing(true);
    setError(null);
    try {
      const result = await api.post(`/v1/system/analyze?auto_remediate=${autoRemediate}`, {});
      setReport(result);
    } catch (err) {
      setError(err.message);
    }
    setAnalyzing(false);
  };

  const runReverification = async () => {
    setAnalyzing(true);
    setError(null);
    try {
      const result = await api.post('/v1/system/reverification', {});
      setReport(prev => ({
        ...prev,
        reverification: result
      }));
    } catch (err) {
      setError(err.message);
    }
    setAnalyzing(false);
  };

  const getPostureColor = (rating) => {
    switch (rating) {
      case 'EXCELLENT': return 'text-green-400';
      case 'GOOD': return 'text-green-300';
      case 'FAIR': return 'text-yellow-400';
      case 'POOR': return 'text-orange-400';
      case 'CRITICAL': return 'text-red-400';
      default: return 'text-gray-400';
    }
  };

  const getSeverityColor = (severity) => {
    switch (severity) {
      case 'critical': return 'bg-red-500';
      case 'high': return 'bg-orange-500';
      case 'medium': return 'bg-yellow-500';
      case 'low': return 'bg-blue-500';
      case 'info': return 'bg-gray-500';
      default: return 'bg-gray-500';
    }
  };

  return (
    <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-white font-medium flex items-center gap-2">
          <Scan className="w-5 h-5 text-cyan-400" />
          System-Wide Security Analysis
        </h3>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-gray-400">
            <input
              type="checkbox"
              checked={autoRemediate}
              onChange={(e) => setAutoRemediate(e.target.checked)}
              className="rounded bg-gray-700 border-gray-600"
            />
            Auto-remediate
          </label>
          <button
            onClick={runReverification}
            disabled={analyzing}
            className="flex items-center gap-2 px-3 py-2 bg-purple-600 hover:bg-purple-500 disabled:bg-gray-600 text-white rounded text-sm transition"
          >
            <ShieldCheck className="w-4 h-4" />
            Re-verify Agents
          </button>
          <button
            onClick={runAnalysis}
            disabled={analyzing}
            className="flex items-center gap-2 px-4 py-2 bg-cyan-600 hover:bg-cyan-500 disabled:bg-gray-600 text-white rounded font-medium transition"
          >
            {analyzing ? (
              <RefreshCw className="w-4 h-4 animate-spin" />
            ) : (
              <Play className="w-4 h-4" />
            )}
            {analyzing ? 'Analyzing...' : 'Run Full Analysis'}
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3 bg-red-900/30 border border-red-700 rounded mb-4">
          <p className="text-red-400 text-sm">{error}</p>
        </div>
      )}

      {report && (
        <div className="space-y-4">
          {/* Security Posture Score */}
          <div className="grid grid-cols-4 gap-4">
            <div className="bg-gray-900 rounded p-4 text-center">
              <p className={`text-4xl font-bold ${getPostureColor(report.security_posture?.rating)}`}>
                {report.security_posture?.score || 0}
              </p>
              <p className="text-gray-500 text-xs mt-1">Security Score</p>
              <p className={`text-sm font-medium ${getPostureColor(report.security_posture?.rating)}`}>
                {report.security_posture?.rating || 'N/A'}
              </p>
            </div>
            <div className="bg-gray-900 rounded p-4 text-center">
              <p className="text-4xl font-bold text-red-400">
                {report.findings_by_severity?.critical || 0}
              </p>
              <p className="text-gray-500 text-xs mt-1">Critical</p>
            </div>
            <div className="bg-gray-900 rounded p-4 text-center">
              <p className="text-4xl font-bold text-orange-400">
                {report.findings_by_severity?.high || 0}
              </p>
              <p className="text-gray-500 text-xs mt-1">High</p>
            </div>
            <div className="bg-gray-900 rounded p-4 text-center">
              <p className="text-4xl font-bold text-yellow-400">
                {report.findings_by_severity?.medium || 0}
              </p>
              <p className="text-gray-500 text-xs mt-1">Medium</p>
            </div>
          </div>

          {/* Analysis Summary */}
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-400">
              Analyzed at {new Date(report.timestamp).toLocaleString()}
            </span>
            <span className="text-gray-400">
              {report.finding_count} findings in {report.duration_seconds}s
            </span>
          </div>

          {/* Recommendations */}
          {report.recommendations && report.recommendations.length > 0 && (
            <div className="bg-gray-900 rounded p-3">
              <p className="text-sm font-medium text-white mb-2">Recommendations:</p>
              <ul className="space-y-1">
                {report.recommendations.slice(0, 5).map((rec, i) => (
                  <li key={i} className="text-gray-400 text-sm flex items-start gap-2">
                    <span className="text-cyan-400">•</span>
                    {rec}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Findings Toggle */}
          {report.findings && report.findings.length > 0 && (
            <div>
              <button
                onClick={() => setShowFindings(!showFindings)}
                className="flex items-center gap-2 text-gray-400 hover:text-white text-sm"
              >
                <ChevronRight className={`w-4 h-4 transition ${showFindings ? 'rotate-90' : ''}`} />
                {showFindings ? 'Hide' : 'Show'} all {report.findings.length} findings
              </button>

              {showFindings && (
                <div className="mt-3 space-y-2 max-h-64 overflow-y-auto">
                  {report.findings.map((finding, i) => (
                    <div key={i} className="bg-gray-900 rounded p-3">
                      <div className="flex items-center gap-2 mb-1">
                        <span className={`px-2 py-0.5 rounded text-xs text-white ${getSeverityColor(finding.severity)}`}>
                          {finding.severity}
                        </span>
                        <span className="text-white text-sm font-medium">{finding.title}</span>
                        {finding.auto_remediated && (
                          <span className="px-2 py-0.5 rounded text-xs bg-green-900 text-green-400">Fixed</span>
                        )}
                      </div>
                      <p className="text-gray-400 text-xs">{finding.description}</p>
                      {finding.recommendation && (
                        <p className="text-cyan-400 text-xs mt-1">{finding.recommendation}</p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Re-verification results */}
          {report.reverification && (
            <div className="bg-purple-900/20 border border-purple-700 rounded p-3">
              <p className="text-purple-400 text-sm font-medium mb-2">Re-verification Results:</p>
              <div className="grid grid-cols-4 gap-3 text-center text-sm">
                <div>
                  <p className="text-white font-bold">{report.reverification.checked}</p>
                  <p className="text-gray-500 text-xs">Checked</p>
                </div>
                <div>
                  <p className="text-white font-bold">{report.reverification.verified}</p>
                  <p className="text-gray-500 text-xs">Verified</p>
                </div>
                <div>
                  <p className="text-green-400 font-bold">{report.reverification.passed}</p>
                  <p className="text-gray-500 text-xs">Passed</p>
                </div>
                <div>
                  <p className="text-red-400 font-bold">{report.reverification.failed}</p>
                  <p className="text-gray-500 text-xs">Failed</p>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {!report && !analyzing && (
        <div className="text-center py-8">
          <Scan className="w-12 h-12 text-gray-600 mx-auto mb-3" />
          <p className="text-gray-400">Run a full security analysis to see system health</p>
          <p className="text-gray-500 text-sm mt-1">Analyzes agents, trust levels, federation, and anomalies</p>
        </div>
      )}
    </div>
  );
}

// Main Dashboard
function Dashboard({ onLogout }) {
  const [activeTab, setActiveTab] = useState('overview');
  const [status, setStatus] = useState(null);
  const [approvals, setApprovals] = useState([]);
  const [anomalies, setAnomalies] = useState([]);
  const [anomalySummary, setAnomalySummary] = useState(null);
  const [agents, setAgents] = useState([]);
  const [relationships, setRelationships] = useState([]);
  const [loading, setLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState(null);
  
  const fetchData = async () => {
    setLoading(true);
    try {
      const [statusRes, approvalsRes, anomaliesRes, summaryRes, agentsRes, fedRes] = await Promise.all([
        api.get('/v1/system/status'),
        api.get('/v1/approvals/'),
        api.get('/v1/anomalies/'),
        api.get('/v1/anomalies/dashboard/summary'),
        api.get('/v1/agents/'),
        api.get('/v1/federation/relationships')
      ]);
      
      setStatus(statusRes);
      setApprovals(approvalsRes.pending_requests || []);
      setAnomalies(anomaliesRes.anomalies || []);
      setAnomalySummary(summaryRes);
      setAgents(agentsRes.agents || []);
      setRelationships(fedRes.relationships || []);
      setLastRefresh(new Date());
    } catch (err) {
      console.error('Failed to fetch data:', err);
    }
    setLoading(false);
  };
  
  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, []);
  
  const handleApprovalComplete = (id) => {
    setApprovals(prev => prev.filter(a => a.request_id !== id));
  };
  
  const handleAnomalyResolved = (id) => {
    setAnomalies(prev => prev.filter(a => a.anomaly_id !== id));
  };
  
  const tabs = [
    { id: 'overview', label: 'Overview', icon: Activity },
    { id: 'approvals', label: 'Approvals', icon: CheckCircle, badge: approvals.length },
    { id: 'anomalies', label: 'Anomalies', icon: AlertTriangle, badge: anomalies.length },
    { id: 'agents', label: 'Agents', icon: Zap },
    { id: 'federation', label: 'Federation', icon: Link2 },
    { id: 'analytics', label: 'Analytics', icon: BarChart3 }
  ];
  
  return (
    <div className="min-h-screen bg-gray-900">
      {/* Header */}
      <header className="bg-gray-800 border-b border-gray-700 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Shield className="w-8 h-8 text-cyan-400" />
            <div>
              <h1 className="text-xl font-bold text-white">AI_NAS_OS</h1>
              <p className="text-gray-500 text-xs">Zero-Trust Agent Platform v{status?.version || '3.0.0'}</p>
            </div>
          </div>
          
          <div className="flex items-center gap-4">
            <button
              onClick={fetchData}
              disabled={loading}
              className="flex items-center gap-2 text-gray-400 hover:text-white transition"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              <span className="text-sm">
                {lastRefresh ? `Updated ${lastRefresh.toLocaleTimeString()}` : 'Refresh'}
              </span>
            </button>
            
            <button
              onClick={onLogout}
              className="text-gray-400 hover:text-white text-sm transition"
            >
              Logout
            </button>
          </div>
        </div>
      </header>
      
      {/* Navigation */}
      <nav className="bg-gray-800 border-b border-gray-700 px-6">
        <div className="flex gap-1">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-3 text-sm font-medium transition border-b-2 ${
                activeTab === tab.id
                  ? 'text-cyan-400 border-cyan-400'
                  : 'text-gray-400 border-transparent hover:text-white'
              }`}
            >
              <tab.icon className="w-4 h-4" />
              {tab.label}
              {tab.badge > 0 && (
                <span className="bg-red-500 text-white text-xs px-1.5 py-0.5 rounded-full">
                  {tab.badge}
                </span>
              )}
            </button>
          ))}
        </div>
      </nav>
      
      {/* Content */}
      <main className="p-6">
        {/* Overview Tab */}
        {activeTab === 'overview' && (
          <div>
            {/* Status Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
              <StatusCard
                title="System Status"
                value={status?.status === 'healthy' ? 'Healthy' : 'Degraded'}
                icon={Server}
                color={status?.status === 'healthy' ? 'text-green-400' : 'text-red-400'}
              />
              <StatusCard
                title="Pending Approvals"
                value={approvals.length}
                icon={Clock}
                color={approvals.length > 0 ? 'text-yellow-400' : 'text-green-400'}
                subtitle={approvals.filter(a => a.priority === 'urgent').length > 0 
                  ? `${approvals.filter(a => a.priority === 'urgent').length} urgent` 
                  : 'None urgent'}
              />
              <StatusCard
                title="Unresolved Anomalies"
                value={anomalySummary?.total_unresolved || 0}
                icon={AlertTriangle}
                color={anomalySummary?.total_unresolved > 0 ? 'text-orange-400' : 'text-green-400'}
                subtitle={anomalySummary?.requires_human_review > 0 
                  ? `${anomalySummary.requires_human_review} need review` 
                  : 'None need review'}
              />
              <StatusCard
                title="Registered Agents"
                value={status?.security_status?.registered_agents || agents.length}
                icon={Users}
                color="text-cyan-400"
              />
            </div>
            
            {/* Security Status Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Anomaly Summary */}
              <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
                <h3 className="text-white font-medium mb-4 flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-orange-400" />
                  Anomaly Summary
                </h3>
                
                {anomalySummary && (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-gray-400 text-sm">By Severity</span>
                    </div>
                    <div className="grid grid-cols-4 gap-2">
                      {['critical', 'high', 'medium', 'low'].map(sev => (
                        <div key={sev} className="bg-gray-900 rounded p-2 text-center">
                          <div className={`w-2 h-2 rounded-full ${severityColors[sev]} mx-auto mb-1`} />
                          <p className="text-white font-medium">{anomalySummary.by_severity?.[sev] || 0}</p>
                          <p className="text-gray-500 text-xs capitalize">{sev}</p>
                        </div>
                      ))}
                    </div>
                    
                    {anomalySummary.by_type && Object.keys(anomalySummary.by_type).length > 0 && (
                      <div className="pt-3 border-t border-gray-700">
                        <span className="text-gray-400 text-sm">By Type</span>
                        <div className="mt-2 space-y-1">
                          {Object.entries(anomalySummary.by_type).map(([type, count]) => (
                            <div key={type} className="flex items-center justify-between text-sm">
                              <span className="text-gray-400">{type}</span>
                              <span className="text-white">{count}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
              
              {/* Recent Activity */}
              <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
                <h3 className="text-white font-medium mb-4 flex items-center gap-2">
                  <Bell className="w-4 h-4 text-cyan-400" />
                  Pending Actions
                </h3>
                
                {approvals.length === 0 && anomalies.filter(a => a.requires_human_review).length === 0 ? (
                  <p className="text-gray-500 text-sm">No pending actions requiring attention</p>
                ) : (
                  <div className="space-y-2">
                    {approvals.slice(0, 3).map(req => (
                      <div key={req.request_id} className="flex items-center justify-between bg-gray-900 rounded p-2">
                        <div className="flex items-center gap-2">
                          <Clock className="w-4 h-4 text-yellow-400" />
                          <span className="text-gray-300 text-sm">{req.action}</span>
                        </div>
                        <span className={`px-2 py-0.5 rounded text-xs text-white ${priorityColors[req.priority]}`}>
                          {req.priority}
                        </span>
                      </div>
                    ))}
                    {anomalies.filter(a => a.requires_human_review).slice(0, 2).map(anom => (
                      <div key={anom.anomaly_id} className="flex items-center justify-between bg-gray-900 rounded p-2">
                        <div className="flex items-center gap-2">
                          <AlertTriangle className="w-4 h-4 text-orange-400" />
                          <span className="text-gray-300 text-sm">{anom.anomaly_type}</span>
                        </div>
                        <span className={`px-2 py-0.5 rounded text-xs text-white ${severityColors[anom.severity]}`}>
                          {anom.severity}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
            
            {/* Services Status */}
            {status?.services && (
              <div className="mt-6 bg-gray-800 rounded-lg p-4 border border-gray-700">
                <h3 className="text-white font-medium mb-4 flex items-center gap-2">
                  <Server className="w-4 h-4 text-cyan-400" />
                  Services
                </h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {Object.entries(status.services).map(([service, serviceStatus]) => (
                    <div key={service} className="flex items-center gap-2">
                      <span className={`w-2 h-2 rounded-full ${serviceStatus === 'healthy' ? 'bg-green-400' : 'bg-red-400'}`} />
                      <span className="text-gray-300 text-sm capitalize">{service}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Anomaly Heatmap */}
            <div className="mt-6 bg-gray-800 rounded-lg p-4 border border-gray-700">
              <h3 className="text-white font-medium mb-4 flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-orange-400" />
                Anomaly Activity (24h)
              </h3>
              <AnomalyHeatmap anomalies={anomalies} agents={agents} />
            </div>
          </div>
        )}
        
        {/* Approvals Tab */}
        {activeTab === 'approvals' && (
          <div>
            <h2 className="text-xl font-bold text-white mb-4">
              Pending Approvals
              {approvals.length > 0 && (
                <span className="text-gray-500 text-sm font-normal ml-2">
                  ({approvals.length} pending)
                </span>
              )}
            </h2>

            {/* Approval Queue Analytics */}
            {approvals.length > 0 && (
              <div className="bg-gray-800 rounded-lg p-4 border border-gray-700 mb-6">
                <h3 className="text-white font-medium mb-4 flex items-center gap-2">
                  <Clock className="w-4 h-4 text-yellow-400" />
                  Queue Status
                </h3>
                <ApprovalQueue approvals={approvals} />
              </div>
            )}

            {approvals.length === 0 ? (
              <div className="bg-gray-800 rounded-lg p-8 border border-gray-700 text-center">
                <CheckCircle className="w-12 h-12 text-green-400 mx-auto mb-4" />
                <p className="text-gray-400">No pending approval requests</p>
                <p className="text-gray-500 text-sm mt-1">All clear - agents are operating within approved parameters</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {approvals.map(req => (
                  <ApprovalCard
                    key={req.request_id}
                    request={req}
                    onApprove={handleApprovalComplete}
                    onReject={handleApprovalComplete}
                  />
                ))}
              </div>
            )}
          </div>
        )}
        
        {/* Anomalies Tab */}
        {activeTab === 'anomalies' && (
          <div>
            <h2 className="text-xl font-bold text-white mb-4">
              Anomaly Detection
              {anomalies.length > 0 && (
                <span className="text-gray-500 text-sm font-normal ml-2">
                  ({anomalies.length} unresolved)
                </span>
              )}
            </h2>
            
            {anomalies.length === 0 ? (
              <div className="bg-gray-800 rounded-lg p-8 border border-gray-700 text-center">
                <Shield className="w-12 h-12 text-green-400 mx-auto mb-4" />
                <p className="text-gray-400">No anomalies detected</p>
                <p className="text-gray-500 text-sm mt-1">Agent behavior is within normal parameters</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {anomalies.map(anom => (
                  <AnomalyCard
                    key={anom.anomaly_id}
                    anomaly={anom}
                    onResolve={handleAnomalyResolved}
                  />
                ))}
              </div>
            )}
          </div>
        )}
        
        {/* Agents Tab */}
        {activeTab === 'agents' && (
          <div>
            <h2 className="text-xl font-bold text-white mb-4">
              Registered Agents
              <span className="text-gray-500 text-sm font-normal ml-2">
                ({agents.length} active)
              </span>
            </h2>

            {/* Trust Level Summary */}
            {agents.length > 0 && (
              <div className="grid grid-cols-4 gap-4 mb-6">
                {['quarantine', 'probation', 'resident', 'citizen'].map(level => {
                  const count = agents.filter(a => (a.trust_level || 'quarantine') === level).length;
                  const colors = trustLevelColors[level];
                  return (
                    <div key={level} className={`rounded-lg p-3 ${colors.bg} border ${colors.border}`}>
                      <div className="flex items-center justify-between">
                        <span className={`text-sm capitalize ${colors.text}`}>{level}</span>
                        <span className="text-white font-bold text-lg">{count}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {agents.length === 0 ? (
              <div className="bg-gray-800 rounded-lg p-8 border border-gray-700 text-center">
                <Zap className="w-12 h-12 text-gray-600 mx-auto mb-4" />
                <p className="text-gray-400">No agents registered</p>
                <p className="text-gray-500 text-sm mt-1">Agents will appear here when they initialize</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {agents.map(agent => (
                  <EnhancedAgentCard key={agent.agent_id} agent={agent} />
                ))}
              </div>
            )}
          </div>
        )}
        
        {/* Federation Tab */}
        {activeTab === 'federation' && (
          <div>
            <h2 className="text-xl font-bold text-white mb-4">
              Federation Relationships
              <span className="text-gray-500 text-sm font-normal ml-2">
                ({relationships.filter(r => r.status === 'established').length} active)
              </span>
            </h2>

            {/* Trust Graph */}
            <div className="bg-gray-800 rounded-lg p-4 border border-gray-700 mb-6">
              <h3 className="text-white font-medium mb-4 flex items-center gap-2">
                <Network className="w-4 h-4 text-purple-400" />
                Federation Trust Graph
              </h3>
              <FederationTrustGraph relationships={relationships} instanceId={status?.instance_id} />
            </div>

            {relationships.length === 0 ? (
              <div className="bg-gray-800 rounded-lg p-8 border border-gray-700 text-center">
                <Link2 className="w-12 h-12 text-gray-600 mx-auto mb-4" />
                <p className="text-gray-400">No federation relationships</p>
                <p className="text-gray-500 text-sm mt-1">Create a trust invitation to connect with another AI_NAS_OS instance</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {relationships.map((rel, i) => (
                  <FederationCard key={rel.relationship_id || i} relationship={rel} />
                ))}
              </div>
            )}
          </div>
        )}

        {/* Analytics Tab */}
        {activeTab === 'analytics' && (
          <div>
            <h2 className="text-xl font-bold text-white mb-4">
              Security Analytics
            </h2>

            {/* System-Wide Analysis Section */}
            <SystemAnalysisPanel />

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
              {/* Capability Analytics */}
              <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
                <h3 className="text-white font-medium mb-4 flex items-center gap-2">
                  <Key className="w-4 h-4 text-cyan-400" />
                  Capability Distribution
                </h3>
                <CapabilityAnalytics agents={agents} />
              </div>

              {/* Approval Queue Stats */}
              <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
                <h3 className="text-white font-medium mb-4 flex items-center gap-2">
                  <Clock className="w-4 h-4 text-yellow-400" />
                  Approval Queue
                </h3>
                <ApprovalQueue approvals={approvals} />
              </div>

              {/* Anomaly Heatmap Full */}
              <div className="bg-gray-800 rounded-lg p-4 border border-gray-700 lg:col-span-2">
                <h3 className="text-white font-medium mb-4 flex items-center gap-2">
                  <TrendingUp className="w-4 h-4 text-orange-400" />
                  Agent Anomaly Heatmap (24h)
                </h3>
                <AnomalyHeatmap anomalies={anomalies} agents={agents} />
              </div>

              {/* Trust Level Distribution */}
              <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
                <h3 className="text-white font-medium mb-4 flex items-center gap-2">
                  <Shield className="w-4 h-4 text-green-400" />
                  Trust Level Distribution
                </h3>
                <div className="space-y-3">
                  {['citizen', 'resident', 'probation', 'quarantine'].map(level => {
                    const count = agents.filter(a => (a.trust_level || 'quarantine') === level).length;
                    const percentage = agents.length > 0 ? (count / agents.length * 100).toFixed(0) : 0;
                    const colors = trustLevelColors[level];
                    return (
                      <div key={level}>
                        <div className="flex items-center justify-between mb-1">
                          <span className={`text-sm capitalize ${colors.text}`}>{level}</span>
                          <span className="text-white text-sm">{count} ({percentage}%)</span>
                        </div>
                        <div className="w-full h-2 bg-gray-700 rounded">
                          <div
                            className={`h-2 rounded ${colors.bg.replace('/50', '')}`}
                            style={{ width: `${percentage}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Federation Health */}
              <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
                <h3 className="text-white font-medium mb-4 flex items-center gap-2">
                  <Link2 className="w-4 h-4 text-purple-400" />
                  Federation Health
                </h3>
                <div className="grid grid-cols-3 gap-3">
                  <div className="bg-gray-900 rounded p-3 text-center">
                    <p className="text-2xl font-bold text-green-400">
                      {relationships.filter(r => r.status === 'established').length}
                    </p>
                    <p className="text-gray-500 text-xs">Established</p>
                  </div>
                  <div className="bg-gray-900 rounded p-3 text-center">
                    <p className="text-2xl font-bold text-yellow-400">
                      {relationships.filter(r => r.status.includes('pending')).length}
                    </p>
                    <p className="text-gray-500 text-xs">Pending</p>
                  </div>
                  <div className="bg-gray-900 rounded p-3 text-center">
                    <p className="text-2xl font-bold text-red-400">
                      {relationships.filter(r => r.status === 'revoked').length}
                    </p>
                    <p className="text-gray-500 text-xs">Revoked</p>
                  </div>
                </div>
                <div className="mt-4 pt-4 border-t border-gray-700">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-400">Total Messages Sent</span>
                    <span className="text-cyan-400">
                      {relationships.reduce((sum, r) => sum + (r.messages_sent || 0), 0)}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-sm mt-2">
                    <span className="text-gray-400">Total Messages Received</span>
                    <span className="text-blue-400">
                      {relationships.reduce((sum, r) => sum + (r.messages_received || 0), 0)}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
      
      {/* Footer */}
      <footer className="bg-gray-800 border-t border-gray-700 px-6 py-3 mt-auto">
        <p className="text-gray-500 text-xs text-center">
          AI_NAS_OS by Quietfire AI • Zero-Trust Agent Platform • Bellevue, Ohio
        </p>
      </footer>
    </div>
  );
}

// Main App
export default function App() {
  const [authenticated, setAuthenticated] = useState(false);
  
  useEffect(() => {
    const key = localStorage.getItem('api_key');
    if (key) {
      api.get('/v1/system/status')
        .then(() => setAuthenticated(true))
        .catch(() => localStorage.removeItem('api_key'));
    }
  }, []);
  
  const handleLogout = () => {
    localStorage.removeItem('api_key');
    setAuthenticated(false);
  };
  
  if (!authenticated) {
    return <LoginScreen onLogin={() => setAuthenticated(true)} />;
  }
  
  return <Dashboard onLogout={handleLogout} />;
}
