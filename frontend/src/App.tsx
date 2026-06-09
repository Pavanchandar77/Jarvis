declare global {
  interface Window {
    electronAPI?: {
      openApp: (name: string) => Promise<{ success: boolean; error?: string }>;
      openFolder: (path: string) => Promise<{ success: boolean; error?: string }>;
      openFile: (path: string) => Promise<{ success: boolean; error?: string }>;
      showNotification: (title: string, body: string) => void;
      windowControl: (action: 'minimize' | 'hide' | 'show' | 'close') => void;
      onServerEvent: (callback: (payload: any) => void) => void;
      onVoiceToggle: (callback: () => void) => void;
      onApproveTask: (callback: () => void) => void;
    };
  }
}

import { useState, useEffect, useRef } from 'react';
import { 
  Play, 
  Pause, 
  Square, 
  FileText, 
  Activity, 
  Terminal, 
  Send, 
  X, 
  Folder, 
  AlertTriangle,
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  Check,
  Shield,
  Lock,
  Unlock,
  Globe,
  WifiOff,
  Database
} from 'lucide-react';

interface Task {
  id: string;
  title: string;
  description: string;
  worker_type: string;
  state: string;
  error_msg?: string;
}

interface Message {
  id: string;
  role: 'user' | 'jarvis';
  content: string;
  isStreaming?: boolean;
  mode?: string;
  voiceContent?: string;
}

interface WorkflowStatus {
  objective: string;
  objective_id: string;
  status: string;
  progress: number;
  completed_tasks: number;
  total_tasks: number;
  active_task: string | null;
}

interface ArtifactList {
  draft_artifacts: string[];
  final_deliverables: string[];
}

const BACKEND_URL = 'http://127.0.0.1:8765';

interface CentralOrbProps {
  state: 'idle' | 'listening' | 'thinking' | 'speaking';
  size?: number;
}

function CentralOrb({ state, size = 260 }: CentralOrbProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animFrame = useRef<number>(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d')!;
    canvas.width = size;
    canvas.height = size;
    const cx = size / 2;
    const cy = size / 2;
    const scale = size / 260;

    const STATE_COLORS = {
      idle: { r: 0, g: 240, b: 255, primary: '#00f0ff' },
      listening: { r: 57, g: 255, b: 20, primary: '#39ff14' },
      thinking: { r: 0, g: 112, b: 243, primary: '#0070f3' },
      speaking: { r: 255, g: 170, b: 0, primary: '#ffaa00' },
    };

    const mode = STATE_COLORS[state] || STATE_COLORS.idle;

    // Orbiting particles
    const particles: { angle: number; radius: number; speed: number; size: number; opacity: number }[] = [];
    for (let i = 0; i < 45; i++) {
      particles.push({
        angle: Math.random() * Math.PI * 2,
        radius: (30 + Math.random() * 50) * scale,
        speed: (Math.random() - 0.5) * 0.012,
        size: (Math.random() * 1.5 + 0.5) * scale,
        opacity: Math.random() * 0.6 + 0.2,
      });
    }

    let time = 0;
    const isActive = state !== 'idle';
    const pulseMultiplier = isActive ? 1.8 : 1.0;

    const draw = () => {
      time += 0.016;
      ctx.clearRect(0, 0, size, size);

      // Outer ring 3 — dashed, slow rotation
      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate(time * 0.08);
      ctx.beginPath();
      ctx.arc(0, 0, 115 * scale, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(${mode.r},${mode.g},${mode.b},0.07)`;
      ctx.lineWidth = 1 * scale;
      ctx.setLineDash([3 * scale, 10 * scale]);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.restore();

      // Outer ring 2 — tick marks
      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate(-time * 0.12);
      for (let i = 0; i < 40; i++) {
        const a = (i / 40) * Math.PI * 2;
        const inner = 98 * scale;
        const outer = i % 5 === 0 ? 107 * scale : 103 * scale;
        const alpha = i % 5 === 0 ? 0.3 : 0.12;
        ctx.beginPath();
        ctx.moveTo(Math.cos(a) * inner, Math.sin(a) * inner);
        ctx.lineTo(Math.cos(a) * outer, Math.sin(a) * outer);
        ctx.strokeStyle = `rgba(${mode.r},${mode.g},${mode.b},${alpha})`;
        ctx.lineWidth = i % 5 === 0 ? 1.5 * scale : 0.8 * scale;
        ctx.stroke();
      }
      ctx.restore();

      // Outer ring 1 — main ring, partial arc
      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate(time * 0.18);
      ctx.beginPath();
      ctx.arc(0, 0, 85 * scale, -0.3, Math.PI * 1.7);
      ctx.strokeStyle = `rgba(${mode.r},${mode.g},${mode.b},0.3)`;
      ctx.lineWidth = 2 * scale;
      ctx.stroke();
      ctx.restore();

      // Inner ring 2 — counter-rotating arc
      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate(-time * 0.25);
      ctx.beginPath();
      ctx.arc(0, 0, 68 * scale, 0.5, Math.PI * 1.4);
      ctx.strokeStyle = `rgba(${mode.r},${mode.g},${mode.b},0.2)`;
      ctx.lineWidth = 1.5 * scale;
      ctx.stroke();
      ctx.restore();

      // Inner ring 1 — solid, subtle
      ctx.beginPath();
      ctx.arc(cx, cy, 52 * scale, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(${mode.r},${mode.g},${mode.b},0.15)`;
      ctx.lineWidth = 1 * scale;
      ctx.stroke();

      // Core glow gradient
      const pulse = 1 + Math.sin(time * 2.5 * pulseMultiplier) * 0.12;
      const gradient = ctx.createRadialGradient(cx, cy, 0, cx, cy, 42 * scale * pulse);
      gradient.addColorStop(0, `rgba(${mode.r},${mode.g},${mode.b},0.65)`);
      gradient.addColorStop(0.3, `rgba(${mode.r},${mode.g},${mode.b},0.22)`);
      gradient.addColorStop(0.6, `rgba(${mode.r},${mode.g},${mode.b},0.06)`);
      gradient.addColorStop(1, 'transparent');
      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, size, size);

      // Center bright core
      const coreGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, 10 * scale * pulse);
      coreGrad.addColorStop(0, `rgba(255,255,255,0.95)`);
      coreGrad.addColorStop(0.4, `rgba(${mode.r},${mode.g},${mode.b},0.65)`);
      coreGrad.addColorStop(1, 'transparent');
      ctx.fillStyle = coreGrad;
      ctx.beginPath();
      ctx.arc(cx, cy, 13 * scale * pulse, 0, Math.PI * 2);
      ctx.fill();

      // Particles orbiting
      for (const p of particles) {
        p.angle += p.speed * pulseMultiplier;
        const px = cx + Math.cos(p.angle) * p.radius;
        const py = cy + Math.sin(p.angle) * p.radius;
        const flickerOpacity = p.opacity * (0.4 + 0.6 * Math.sin(time * 3 + p.angle));
        ctx.fillStyle = `rgba(${mode.r},${mode.g},${mode.b},${flickerOpacity})`;
        ctx.beginPath();
        ctx.arc(px, py, p.size, 0, Math.PI * 2);
        ctx.fill();
      }

      // Crosshair lines
      const chAlpha = 0.08 + Math.sin(time) * 0.03;
      ctx.strokeStyle = `rgba(${mode.r},${mode.g},${mode.b},${chAlpha})`;
      ctx.lineWidth = 0.5 * scale;
      // Horizontal
      ctx.beginPath();
      ctx.moveTo(cx - 120 * scale, cy);
      ctx.lineTo(cx - 18 * scale, cy);
      ctx.moveTo(cx + 18 * scale, cy);
      ctx.lineTo(cx + 120 * scale, cy);
      ctx.stroke();
      // Vertical
      ctx.beginPath();
      ctx.moveTo(cx, cy - 120 * scale);
      ctx.lineTo(cx, cy - 18 * scale);
      ctx.moveTo(cx, cy + 18 * scale);
      ctx.lineTo(cx, cy + 120 * scale);
      ctx.stroke();

      // Corner brackets on the crosshair
      const bracketSize = 7 * scale;
      const bracketDist = 20 * scale;
      ctx.strokeStyle = `rgba(${mode.r},${mode.g},${mode.b},0.2)`;
      ctx.lineWidth = 1 * scale;
      // Top-left
      ctx.beginPath();
      ctx.moveTo(cx - bracketDist, cy - bracketDist - bracketSize);
      ctx.lineTo(cx - bracketDist, cy - bracketDist);
      ctx.lineTo(cx - bracketDist - bracketSize, cy - bracketDist);
      ctx.stroke();
      // Top-right
      ctx.beginPath();
      ctx.moveTo(cx + bracketDist, cy - bracketDist - bracketSize);
      ctx.lineTo(cx + bracketDist, cy - bracketDist);
      ctx.lineTo(cx + bracketDist + bracketSize, cy - bracketDist);
      ctx.stroke();
      // Bottom-left
      ctx.beginPath();
      ctx.moveTo(cx - bracketDist, cy + bracketDist + bracketSize);
      ctx.lineTo(cx - bracketDist, cy + bracketDist);
      ctx.lineTo(cx - bracketDist - bracketSize, cy + bracketDist);
      ctx.stroke();
      // Bottom-right
      ctx.beginPath();
      ctx.moveTo(cx + bracketDist, cy + bracketDist + bracketSize);
      ctx.lineTo(cx + bracketDist, cy + bracketDist);
      ctx.lineTo(cx + bracketDist + bracketSize, cy + bracketDist);
      ctx.stroke();

      animFrame.current = requestAnimationFrame(draw);
    };

    draw();

    return () => cancelAnimationFrame(animFrame.current);
  }, [state, size]);

  const STATE_COLORS = {
    idle: '#00f0ff',
    listening: '#39ff14',
    thinking: '#0070f3',
    speaking: '#ffaa00',
  };

  const glowColor = STATE_COLORS[state] || STATE_COLORS.idle;

  return (
    <div style={{ position: 'relative', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
      <canvas
        ref={canvasRef}
        style={{
          width: `${size}px`,
          height: `${size}px`,
          filter: `drop-shadow(0 0 30px ${glowColor}55)`,
        }}
      />
      <div 
        style={{ 
          position: 'absolute', 
          bottom: '2px', 
          fontFamily: 'JetBrains Mono, monospace', 
          fontSize: '9px', 
          letterSpacing: '2.5px',
          textTransform: 'uppercase',
          color: glowColor,
          opacity: 0.5,
          fontWeight: 500
        }}
      >
        {state === 'idle' ? 'STANDBY' : state}
      </div>
    </div>
  );
}

function HudView() {
  const [activeWorkflow, setActiveWorkflow] = useState<WorkflowStatus | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [cpuTemp, setCpuTemp] = useState(42);
  const [cpuLoad, setCpuLoad] = useState(12);
  const [pingMs, setPingMs] = useState(25);

  useEffect(() => {
    const checkStatus = () => {
      fetch(`${BACKEND_URL}/api/autonomy/status`)
        .then((res) => res.json())
        .then((data) => {
          if (data && data.status !== 'inactive') {
            setActiveWorkflow(data);
            fetch(`${BACKEND_URL}/api/autonomy/tasks?objective_id=${data.objective_id}`)
              .then((res) => res.json())
              .then((tData) => {
                if (tData && tData.tasks) {
                  setTasks(tData.tasks);
                }
              })
              .catch(() => {});
          } else {
            setActiveWorkflow(null);
            setTasks([]);
          }
        })
        .catch(() => {});
    };

    checkStatus();
    const interval = setInterval(checkStatus, 3000);

    if (window.electronAPI) {
      window.electronAPI.onServerEvent(() => {
        checkStatus();
      });
    }

    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const timer = setInterval(() => {
      setCpuTemp(Math.floor(Math.random() * 5) + 40);
      setCpuLoad(Math.floor(Math.random() * 15) + 6);
      setPingMs(Math.floor(Math.random() * 10) + 18);
    }, 4000);
    return () => clearInterval(timer);
  }, []);

  if (!activeWorkflow) {
    return (
      <div className="hud-overlay-container standby">
        <div className="hud-header">
          <div className="hud-title">J.A.R.V.I.S. HUD</div>
          <span className="hud-status standby">STANDBY</span>
        </div>
        <div className="hud-content">
          <div className="hud-label">System Health</div>
          <div className="vitals-row">
            <span>CPU {cpuLoad}%</span>
            <span>TEMP {cpuTemp}°C</span>
            <span>LATENCY {pingMs}ms</span>
          </div>
        </div>
        <div className="hud-scanline" />
      </div>
    );
  }

  const progressPercent = Math.round((activeWorkflow.progress || 0) * 100);
  const activeTask = tasks.find((t) => t.state === 'running');

  return (
    <div className="hud-overlay-container active">
      <div className="hud-header">
        <div className="hud-title truncate" style={{ maxWidth: '180px' }}>
          {activeWorkflow.objective}
        </div>
        <span className={`hud-status ${activeWorkflow.status}`}>
          {activeWorkflow.status.toUpperCase()}
        </span>
      </div>

      <div className="hud-content">
        <div className="hud-progress-bar-bg">
          <div className="hud-progress-bar-fill" style={{ width: `${progressPercent}%` }} />
        </div>
        <div className="hud-progress-text">Progress: {progressPercent}%</div>

        {activeTask && (
          <div className="hud-task-section">
            <div className="hud-label">Executing Task</div>
            <div className="hud-task-title truncate" style={{ maxWidth: '280px' }}>
              {activeTask.title}
            </div>
          </div>
        )}
      </div>
      <div className="hud-scanline" />
    </div>
  );
}

const MarkdownRenderer = ({ content }: { content: string }) => {
  if (!content) return null;
  const lines = content.split('\n');
  return (
    <div className="markdown-body">
      {lines.map((line, idx) => {
        let trimmed = line.trim();
        if (trimmed.startsWith('### ')) {
          return <h4 key={idx} className="md-h4">{renderInline(trimmed.substring(4))}</h4>;
        }
        if (trimmed.startsWith('## ')) {
          return <h3 key={idx} className="md-h3">{renderInline(trimmed.substring(3))}</h3>;
        }
        if (trimmed.startsWith('# ')) {
          return <h2 key={idx} className="md-h2">{renderInline(trimmed.substring(2))}</h2>;
        }
        if (trimmed.startsWith('* ') || trimmed.startsWith('- ')) {
          return <li key={idx} className="md-li">{renderInline(trimmed.substring(2))}</li>;
        }
        if (/^\d+\.\s+/.test(trimmed)) {
          return <li key={idx} className="md-li-num">{renderInline(trimmed.replace(/^\d+\.\s+/, ''))}</li>;
        }
        if (!trimmed) {
          return <div key={idx} style={{ height: '8px' }} />;
        }
        return <p key={idx} className="md-p">{renderInline(line)}</p>;
      })}
    </div>
  );
};

const renderInline = (text: string) => {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i} className="md-strong">{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return <code key={i} className="md-code">{part.slice(1, -1)}</code>;
    }
    return part;
  });
};

const getSuggestionsForMode = (mode: string) => {
  switch (mode) {
    case 'ambient':
      return ["What is the weather tomorrow?", "Weekly outlook", "Current status"];
    case 'deep_research':
      return ["Summarize this report", "Save report to files", "Run another research"];
    case 'operational':
      return ["Run system diagnostics", "Show recent downloads", "Show active tasks"];
    case 'system_control':
      return ["Launch vscode", "Open downloads folder", "Desktop status"];
    case 'conversational':
    default:
      return ["Tell me more", "Explain step-by-step", "Help me brainstorm"];
  }
};

export default function App() {
  const [messages, setMessages] = useState<Message[]>([
    { id: 'init-1', role: 'jarvis', content: 'Calm operational presence online. State your objective, sir.', mode: 'operational' }
  ]);
  const [inputVal, setInputVal] = useState('');
  const [activeWorkflow, setActiveWorkflow] = useState<WorkflowStatus | null>(null);
  const [speakingMessageId, setSpeakingMessageId] = useState<string | null>(null);
  const [activeInteractionMode, setActiveInteractionMode] = useState<string>('conversational');
  const [tasks, setTasks] = useState<Task[]>([]);
  const [artifacts, setArtifacts] = useState<ArtifactList>({ draft_artifacts: [], final_deliverables: [] });
  const [previewFile, setPreviewFile] = useState<{ name: string; type: string; content: string } | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [apiConnected, setApiConnected] = useState(false);
  const [activeTab, setActiveTab] = useState<'tasks' | 'artifacts' | 'security'>('tasks');

  // Phase 10: Security States
  const [securityStatus, setSecurityStatus] = useState<any>(null);
  const [vaultPassword, setVaultPassword] = useState('');
  const [vaultNewKey, setVaultNewKey] = useState('');
  const [vaultNewValue, setVaultNewValue] = useState('');
  const [pendingPermissions, setPendingPermissions] = useState<any[]>([]);
  const [auditLogs, setAuditLogs] = useState<string[]>([]);

  // J.A.R.V.I.S. Voice & Orb HUD states
  const [orbState, setOrbState] = useState<'idle' | 'listening' | 'thinking' | 'speaking'>('idle');
  const [voiceActivationEnabled, setVoiceActivationEnabled] = useState(true);
  const [voiceResponseEnabled, setVoiceResponseEnabled] = useState(true);
  const [chatPanelCollapsed, setChatPanelCollapsed] = useState(true);
  const [cpuTemp, setCpuTemp] = useState(42);
  const [cpuLoad, setCpuLoad] = useState(8);
  const [pingMs, setPingMs] = useState(25);
  const [eventLogs, setEventLogs] = useState<string[]>([]);
  const [eqHeights, setEqHeights] = useState<number[]>(Array(15).fill(4));

  const voiceRef = useRef<SpeechSynthesisVoice | null>(null);
  const recognitionRef = useRef<any>(null);
  const recognitionActiveRef = useRef<boolean>(false);
  
  // Continuous conversational state tracking
  const sessionActiveRef = useRef<boolean>(false);
  const isSpeakingRef = useRef<boolean>(false);
  const activeSpeechCountRef = useRef<number>(0);
  const sessionTimeoutRef = useRef<any>(null);
  
  const spokenIndexRef = useRef<number>(0);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const activeWorkflowRef = useRef<WorkflowStatus | null>(null);
  useEffect(() => {
    activeWorkflowRef.current = activeWorkflow;
  }, [activeWorkflow]);

  const tasksRef = useRef<Task[]>([]);
  useEffect(() => {
    tasksRef.current = tasks;
  }, [tasks]);

  // Poll server connection & active workflow status
  useEffect(() => {
    const checkConnection = () => {
      fetch(`${BACKEND_URL}/health`)
        .then((res) => {
          if (res.ok) setApiConnected(true);
        })
        .catch(() => setApiConnected(false));
    };

    checkConnection();
    const connInterval = setInterval(checkConnection, 10000);
    return () => clearInterval(connInterval);
  }, []);

  // Poll workflow details
  useEffect(() => {
    if (!apiConnected) return;

    const pollWorkflow = () => {
      fetch(`${BACKEND_URL}/api/autonomy/status`)
        .then((res) => res.json())
        .then((data: WorkflowStatus) => {
          if (data && data.status !== 'inactive') {
            setActiveWorkflow(data);
          } else {
            setActiveWorkflow(null);
          }
        })
        .catch(() => {});
    };

    pollWorkflow();
    const pollInterval = setInterval(pollWorkflow, 3000);
    return () => clearInterval(pollInterval);
  }, [apiConnected]);

  // Fetch tasks and artifacts of active workflow
  useEffect(() => {
    if (!activeWorkflow) {
      setTasks([]);
      setArtifacts({ draft_artifacts: [], final_deliverables: [] });
      return;
    }

    const fetchTasksAndArtifacts = () => {
      const objId = activeWorkflow.objective_id;
      
      // Tasks
      fetch(`${BACKEND_URL}/api/autonomy/tasks?objective_id=${objId}`)
        .then((res) => res.json())
        .then((data: { tasks: Task[] }) => {
          if (data && data.tasks) setTasks(data.tasks);
        })
        .catch(() => {});

      // Artifacts
      fetch(`${BACKEND_URL}/api/autonomy/artifacts?objective_id=${objId}`)
        .then((res) => res.json())
        .then((data: ArtifactList) => {
          if (data) setArtifacts(data);
        })
        .catch(() => {});
    };

    fetchTasksAndArtifacts();
    const fetchInterval = setInterval(fetchTasksAndArtifacts, 4000);
    return () => clearInterval(fetchInterval);
  }, [activeWorkflow]);

  // Poll security status, pending permissions, and audit logs
  useEffect(() => {
    if (!apiConnected) return;

    const pollSecurity = () => {
      // 1. General status
      fetch(`${BACKEND_URL}/api/security/status`)
        .then((res) => res.json())
        .then((data) => {
          if (data && data.status === 'ok') {
            setSecurityStatus(data);
          }
        })
        .catch(() => {});

      // 2. Pending permissions
      fetch(`${BACKEND_URL}/api/security/pending-permissions`)
        .then((res) => res.json())
        .then((data) => {
          if (data && data.requests) {
            setPendingPermissions(data.requests);
          }
        })
        .catch(() => {});

      // 3. Audit logs
      fetch(`${BACKEND_URL}/api/security/audit-logs`)
        .then((res) => res.json())
        .then((data) => {
          if (data && data.logs) {
            setAuditLogs(data.logs);
          }
        })
        .catch(() => {});
    };

    pollSecurity();
    const secInterval = setInterval(pollSecurity, 3000);
    return () => clearInterval(secInterval);
  }, [apiConnected]);

  // Hook to auto-switch to deliverables and preview primary output on objective completion
  const prevWorkflowIdRef = useRef<string>('');
  const prevWorkflowStatusRef = useRef<string>('');

  useEffect(() => {
    if (!activeWorkflow) {
      prevWorkflowIdRef.current = '';
      prevWorkflowStatusRef.current = '';
      return;
    }

    const currentId = activeWorkflow.objective_id;
    const currentStatus = activeWorkflow.status;

    if (currentId === prevWorkflowIdRef.current && 
        currentStatus === 'completed' && 
        prevWorkflowStatusRef.current === 'running') {
      
      const objId = currentId;
      fetch(`${BACKEND_URL}/api/autonomy/artifacts?objective_id=${objId}`)
        .then((res) => res.json())
        .then((data: ArtifactList) => {
          if (data && data.final_deliverables && data.final_deliverables.length > 0) {
            setArtifacts(data);
            const firstDeliverable = data.final_deliverables[0];
            fetch(`${BACKEND_URL}/api/autonomy/artifact/content?objective_id=${objId}&filename=${firstDeliverable}&file_type=final`)
              .then((res) => res.json())
              .then((contentData: { content: string }) => {
                if (contentData && contentData.content) {
                  setPreviewFile({ name: firstDeliverable, type: 'final', content: contentData.content });
                  setActiveTab('artifacts');
                }
              })
              .catch(() => {});
          }
        })
        .catch(() => {});
    }

    prevWorkflowIdRef.current = currentId;
    prevWorkflowStatusRef.current = currentStatus;
  }, [activeWorkflow]);

  const handleSetPrivacyMode = (mode: string) => {
    fetch(`${BACKEND_URL}/api/security/privacy/mode`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode })
    })
      .then((res) => res.json())
      .then((data) => {
        if (data && data.status === 'ok') {
          setSecurityStatus((prev: any) => prev ? { ...prev, privacy_mode: mode } : null);
        }
      })
      .catch(() => {});
  };

  const handleUnlockVault = () => {
    fetch(`${BACKEND_URL}/api/security/vault/unlock`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: vaultPassword })
    })
      .then((res) => res.json())
      .then((data) => {
        if (data && data.status === 'ok' && data.unlocked) {
          setVaultPassword('');
        }
      })
      .catch(() => {});
  };

  const handleLockVault = () => {
    fetch(`${BACKEND_URL}/api/security/vault/lock`, {
      method: 'POST'
    })
      .then((res) => res.json())
      .catch(() => {});
  };

  const handleSetSecret = () => {
    if (!vaultNewKey) return;
    fetch(`${BACKEND_URL}/api/security/vault/set`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ key: vaultNewKey, value: vaultNewValue })
    })
      .then((res) => res.json())
      .then((data) => {
        if (data && data.status === 'ok') {
          setVaultNewKey('');
          setVaultNewValue('');
        }
      })
      .catch(() => {});
  };

  const handleResolvePermission = (requestId: string, approve: boolean) => {
    fetch(`${BACKEND_URL}/api/security/approve-permission`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ request_id: requestId, approve })
    })
      .then((res) => res.json())
      .then((data) => {
        if (data && data.status === 'ok') {
          setPendingPermissions((prev) => prev.filter((p) => p.id !== requestId));
        }
      })
      .catch(() => {});
  };

  // Auto-scroll chat window
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Simulate live metrics (CPU Temp and Ping)
  useEffect(() => {
    const timer = setInterval(() => {
      setCpuTemp((prev) => {
        const diff = Math.random() > 0.5 ? 1 : -1;
        const next = prev + diff;
        return next > 52 ? 50 : next < 36 ? 38 : next;
      });
      setCpuLoad((prev) => {
        const diff = Math.floor(Math.random() * 3) - 1;
        const next = prev + diff;
        return next > 25 ? 20 : next < 3 ? 5 : next;
      });
      setPingMs((prev) => {
        const diff = Math.floor(Math.random() * 5) - 2;
        const next = prev + diff;
        return next > 35 ? 30 : next < 12 ? 15 : next;
      });
    }, 2000);
    return () => clearInterval(timer);
  }, []);

  // Equalizer animation matching orbState
  useEffect(() => {
    let interval: any;
    
    if (orbState === 'idle') {
      interval = setInterval(() => {
        setEqHeights(Array.from({ length: 15 }, () => Math.floor(Math.random() * 4) + 4));
      }, 150);
    } else if (orbState === 'listening') {
      interval = setInterval(() => {
        setEqHeights(Array.from({ length: 15 }, () => Math.floor(Math.random() * 15) + 4));
      }, 100);
    } else if (orbState === 'thinking') {
      interval = setInterval(() => {
        setEqHeights(Array.from({ length: 15 }, (_, i) => {
          const time = Date.now() * 0.015;
          const val = Math.sin(time + i * 0.4) * 6 + 10;
          return Math.max(4, Math.floor(val));
        }));
      }, 50);
    } else if (orbState === 'speaking') {
      interval = setInterval(() => {
        setEqHeights(Array.from({ length: 15 }, () => Math.floor(Math.random() * 20) + 4));
      }, 80);
    }

    return () => clearInterval(interval);
  }, [orbState]);

  // Load and select British en-GB voice
  useEffect(() => {
    const selectVoice = () => {
      const voices = window.speechSynthesis.getVoices();
      const gbVoices = voices.filter(v => v.lang.toLowerCase().includes('gb') || v.lang.toLowerCase().includes('en-gb'));
      if (gbVoices.length > 0) {
        const maleVoice = gbVoices.find(v => v.name.toLowerCase().includes('male') || v.name.toLowerCase().includes('google uk english male'));
        voiceRef.current = maleVoice || gbVoices[0];
      } else {
        const enVoices = voices.filter(v => v.lang.toLowerCase().startsWith('en'));
        if (enVoices.length > 0) {
          const maleVoice = enVoices.find(v => v.name.toLowerCase().includes('male'));
          voiceRef.current = maleVoice || enVoices[0];
        }
      }
    };

    selectVoice();
    if (window.speechSynthesis.onvoiceschanged !== undefined) {
      window.speechSynthesis.onvoiceschanged = selectVoice;
    }
  }, []);

  // Voice execution helper
  const cancelSpeech = () => {
    window.speechSynthesis.cancel();
    activeSpeechCountRef.current = 0;
    isSpeakingRef.current = false;
    setSpeakingMessageId(null);
  };

  const cancelSpeechAndSession = () => {
    cancelSpeech();
    sessionActiveRef.current = false;
    if (sessionTimeoutRef.current) clearTimeout(sessionTimeoutRef.current);
    setOrbState('idle');
  };

  const startSessionTimer = () => {
    if (sessionTimeoutRef.current) clearTimeout(sessionTimeoutRef.current);
    sessionTimeoutRef.current = setTimeout(() => {
      if (sessionActiveRef.current) {
        sessionActiveRef.current = false;
        speakText("Standing by, sir.");
      }
    }, 15000); // Wait 15 seconds of silence before dropping session
  };

  // Helper to read text aloud
  const speakText = (text: string, onStart?: () => void, onEnd?: () => void, messageId?: string) => {
    if (!voiceResponseEnabled) {
      if (onEnd) onEnd();
      return;
    }

    // Clean up Markdown and layout tags
    let cleanText = text
      .replace(/```[\s\S]*?```/g, '[Code block content, sir]')
      .replace(/`([^`]+)`/g, '$1')
      .replace(/\*\*([^*]+)\*\*/g, '$1')
      .replace(/\*([^*]+)\*/g, '$1')
      .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
      .replace(/#+\s+/g, '')
      .trim();

    if (!cleanText) {
      if (onEnd) onEnd();
      return;
    }

    const utterance = new SpeechSynthesisUtterance(cleanText);
    if (voiceRef.current) {
      utterance.voice = voiceRef.current;
    }
    utterance.rate = 1.05;
    utterance.pitch = 0.95;

    utterance.onstart = () => {
      isSpeakingRef.current = true;
      setOrbState('speaking');
      if (messageId) setSpeakingMessageId(messageId);
      if (onStart) onStart();
    };

    const handleSpeechEnd = () => {
      activeSpeechCountRef.current = Math.max(0, activeSpeechCountRef.current - 1);
      if (activeSpeechCountRef.current === 0) {
        isSpeakingRef.current = false;
        setSpeakingMessageId(null);
        if (sessionActiveRef.current) {
          setOrbState('listening');
          startSessionTimer();
        } else {
          setOrbState('idle');
        }
      }
      if (onEnd) onEnd();
    };

    utterance.onend = handleSpeechEnd;
    utterance.onerror = handleSpeechEnd;

    activeSpeechCountRef.current += 1;
    isSpeakingRef.current = true;
    setOrbState('speaking');

    window.speechSynthesis.speak(utterance);
  };

  // Play confirmation upon toggle settings
  useEffect(() => {
    if (voiceResponseEnabled) {
      setTimeout(() => {
        cancelSpeech();
        speakText("Speech synthesis online, sir.");
      }, 100);
    } else {
      cancelSpeech();
    }
  }, [voiceResponseEnabled]);

  useEffect(() => {
    if (voiceActivationEnabled) {
      speakText("Voice activation system listening, sir.");
    }
  }, [voiceActivationEnabled]);

  // Reset session when voice activation is toggled off
  useEffect(() => {
    if (!voiceActivationEnabled) {
      sessionActiveRef.current = false;
      if (sessionTimeoutRef.current) clearTimeout(sessionTimeoutRef.current);
      setOrbState('idle');
    }
  }, [voiceActivationEnabled]);

  // Watchdog Keep-Alive Timer disabled to prevent clashing loops
  useEffect(() => {
    // Disabled watchdog
  }, [voiceActivationEnabled]);

  // Continuous Speech Recognition Hook
  useEffect(() => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) return;

    const rec = new SpeechRecognition();
    rec.continuous = true;
    rec.interimResults = false;
    rec.lang = 'en-US';

    rec.onstart = () => {
      recognitionActiveRef.current = true;
    };

    rec.onend = () => {
      recognitionActiveRef.current = false;
      if (voiceActivationEnabled) {
        // Delayed restart to let the browser release the audio context cleanly
        setTimeout(() => {
          if (voiceActivationEnabled && !recognitionActiveRef.current) {
            try {
              rec.start();
            } catch (e) {
              console.error("Delayed restart failed:", e);
            }
          }
        }, 400);
      }
    };

    rec.onerror = (event: any) => {
      console.error("Speech recognition error:", event.error);
      if (event.error === 'not-allowed') {
        setVoiceActivationEnabled(false);
      }
    };

    rec.onresult = (event: any) => {
      const transcript = event.results[event.resultIndex][0].transcript.trim();
      if (!transcript) return;

      console.log("J.A.R.V.I.S. STT Heard:", transcript);

      // Interruption Support: If Jarvis is speaking and the user speaks, interrupt immediately
      if (isSpeakingRef.current) {
        console.log("User interrupted J.A.R.V.I.S. speech!");
        cancelSpeech();
        isSpeakingRef.current = false;
        
        const lowerT = transcript.toLowerCase().replace(/^(jarvis|jarves|jarve|jarv|java|travis|harvis|gervis|charvis|jarviss|j\.a\.r\.v\.i\.s\.)[,.!?\s]*/, '').trim();
        if (lowerT === 'stop' || lowerT === 'quiet' || lowerT === 'shut up' || lowerT === 'nevermind') {
          speakText("Standing by, sir.");
          return;
        }
        // Fall through to process the interruption command
      }

      // Ignore results if thinking or sending to prevent self-triggering
      if (orbState === 'thinking' || isSending) {
        console.log("Speech recognition result ignored (busy thinking/sending).");
        return;
      }

      // ── Voice Task Approval Check ──────────────────────────────────────────
      const isAwaitingApproval = tasksRef.current.some((t) => t.state === 'awaiting_approval');
      if (isAwaitingApproval) {
        const lowerTranscript = transcript.toLowerCase();
        const cleanText = lowerTranscript
          .replace(/^(jarvis|jarves|jarve|jarv|java|travis|harvis|gervis|charvis|jarviss|j\.a\.r\.v\.i\.s\.)[,.!?\s]*/, '')
          .trim();
        
        if (
          cleanText === 'approve' || 
          cleanText === 'yes' || 
          cleanText === 'go ahead' || 
          cleanText === 'proceed' || 
          cleanText === 'do it' ||
          cleanText === 'approve step' ||
          cleanText === 'approve task'
        ) {
          console.log("STT Voice Approval matched:", cleanText);
          cancelSpeech();
          triggerWorkflowControl('approve');
          speakText("Proceeding, sir.");
          return;
        }
      }

      // Handle active conversational session (no wake word required)
      if (sessionActiveRef.current) {
        if (sessionTimeoutRef.current) clearTimeout(sessionTimeoutRef.current);
        handleSendMessage(transcript);
        return;
      }

      // Handle wake-word detection with phonetic fallbacks to accommodate accent/transcription inaccuracies
      const lowerTranscript = transcript.toLowerCase();
      const wakeWords = ['jarvis', 'jarves', 'jarve', 'jarv', 'java', 'travis', 'harvis', 'gervis', 'charvis', 'jarviss', 'j.a.r.v.i.s.'];
      
      let detectedWakeWord = '';
      for (const word of wakeWords) {
        if (lowerTranscript.includes(word)) {
          detectedWakeWord = word;
          break;
        }
      }

      if (detectedWakeWord) {
        cancelSpeech();
        sessionActiveRef.current = true;
        
        const jarvisIndex = lowerTranscript.indexOf(detectedWakeWord);
        const cmd = transcript.substring(jarvisIndex + detectedWakeWord.length).trim();
        const cleanedCmd = cmd.replace(/^[,.!?\s]+/, '');

        if (cleanedCmd.length > 0) {
          handleSendMessage(cleanedCmd);
        } else {
          speakText("Yes, sir?");
        }
      }
    };

    recognitionRef.current = rec;

    if (voiceActivationEnabled) {
      try {
        rec.start();
      } catch (e) {
        console.error("Failed to start speech recognition:", e);
      }
    }

    return () => {
      rec.onstart = null;
      rec.onend = null;
      rec.onerror = null;
      rec.onresult = null;
      try {
        rec.stop();
      } catch (e) {}
    };
  }, [voiceActivationEnabled]);

  // Send a message via streaming API
  const handleSendMessage = async (overridePrompt?: string) => {
    const promptToSend = overridePrompt || inputVal;
    if (!promptToSend.trim() || isSending) return;
    
    if (overridePrompt) {
      if (sessionTimeoutRef.current) clearTimeout(sessionTimeoutRef.current);
      cancelSpeech();
    } else {
      cancelSpeechAndSession();
      setInputVal('');
    }
    
    setIsSending(true);
    setOrbState('thinking');
    spokenIndexRef.current = 0;

    // Generate deterministic unique IDs to avoid stale React state array mappings
    const userMsgId = 'user-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
    const jarvisMsgId = 'jarvis-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);

    setMessages((prev) => [
      ...prev, 
      { id: userMsgId, role: 'user', content: promptToSend },
      { id: jarvisMsgId, role: 'jarvis', content: '...', isStreaming: true }
    ]);
    
    // Check if it is likely to trigger an autonomy workflow
    const isAutonomyGoal = 
      (promptToSend.toLowerCase().includes('create') || promptToSend.toLowerCase().includes('generate') || promptToSend.toLowerCase().includes('write')) &&
      (promptToSend.toLowerCase().includes('research') || promptToSend.toLowerCase().includes('learn') || promptToSend.toLowerCase().includes('proficient'));

    try {
      const response = await fetch(`${BACKEND_URL}/v1/chat/completions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: [{ role: 'user', content: promptToSend }],
          stream: true
        })
      });

      if (!response.body) throw new Error('No stream body received.');

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let fullText = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const cleanLine = line.trim();
          if (!cleanLine || cleanLine === 'data: [DONE]') continue;
          if (cleanLine.startsWith('data: ')) {
            try {
              const parsed = JSON.parse(cleanLine.substring(6));
              const delta = parsed.choices?.[0]?.delta?.content || '';
              fullText += delta;
              
              // Parse out dual responses from streaming buffer
              let extractedMode = 'conversational';
              let extractedUI = '';
              let extractedVoice = '';
              let hasDelimiters = false;

              if (fullText.includes('[INTERACTION_MODE]')) {
                hasDelimiters = true;
                const parts = fullText.split('[INTERACTION_MODE]');
                const remaining = parts[1] || '';
                const newlineIdx = remaining.indexOf('\n');
                extractedMode = newlineIdx !== -1 ? remaining.substring(0, newlineIdx).trim() : remaining.trim();

                if (remaining.includes('[UI_RESPONSE]')) {
                  const uiParts = remaining.split('[UI_RESPONSE]\n');
                  const uiSection = uiParts[1] || '';
                  if (uiSection.includes('[VOICE_RESPONSE]')) {
                    const voiceParts = uiSection.split('[VOICE_RESPONSE]\n');
                    extractedUI = voiceParts[0].trim();
                    extractedVoice = voiceParts[1].trim();
                  } else {
                    extractedUI = uiSection.trim();
                  }
                }
              }

              const displayContent = hasDelimiters ? extractedUI : fullText;
              setActiveInteractionMode(extractedMode);

              setMessages((prev) => {
                return prev.map(m => m.id === jarvisMsgId ? { 
                  ...m, 
                  content: displayContent || '...', 
                  isStreaming: true,
                  mode: extractedMode,
                  voiceContent: extractedVoice
                } : m);
              });

              // Process streaming text sentence-by-sentence for voice
              if (voiceResponseEnabled) {
                const targetText = hasDelimiters ? extractedVoice : fullText;
                const textToScan = targetText.substring(spokenIndexRef.current);
                const match = textToScan.match(/[.!?](?:\s+|\n)|(?:\n\n)/);
                if (match && match.index !== undefined) {
                  const sentenceLength = match.index + match[0].length;
                  const sentence = textToScan.substring(0, sentenceLength).trim();
                  spokenIndexRef.current += sentenceLength;
                  if (sentence) {
                    speakText(sentence, undefined, undefined, jarvisMsgId);
                  }
                }
              }
            } catch (err) {
              // skip malformed JSON chunks
            }
          }
        }
      }

      let finalMode = 'conversational';
      let finalUI = fullText;
      let finalVoice = '';
      let hasDelims = false;

      if (fullText.includes('[INTERACTION_MODE]')) {
        hasDelims = true;
        const parts = fullText.split('[INTERACTION_MODE]');
        const remaining = parts[1] || '';
        const newlineIdx = remaining.indexOf('\n');
        finalMode = newlineIdx !== -1 ? remaining.substring(0, newlineIdx).trim() : remaining.trim();
        const uiSection = remaining.split('[UI_RESPONSE]\n')[1] || '';
        const voiceParts = uiSection.split('[VOICE_RESPONSE]\n');
        finalUI = voiceParts[0].trim();
        finalVoice = voiceParts[1].trim();
      }

      setActiveInteractionMode(finalMode);

      setMessages((prev) => {
        return prev.map(m => m.id === jarvisMsgId ? { 
          ...m, 
          content: finalUI || 'Command resolved.', 
          isStreaming: false,
          mode: finalMode,
          voiceContent: finalVoice
        } : m);
      });

      // Read remaining text if any
      const finalTarget = hasDelims ? finalVoice : fullText;
      if (voiceResponseEnabled && spokenIndexRef.current < finalTarget.length) {
        const remaining = finalTarget.substring(spokenIndexRef.current).trim();
        if (remaining) {
          speakText(remaining, undefined, undefined, jarvisMsgId);
        }
      }

      // If we launched an autonomy workflow, trigger status refresh
      if (isAutonomyGoal) {
        setTimeout(() => {
          fetch(`${BACKEND_URL}/api/autonomy/status`)
            .then(res => res.json())
            .then(data => { if (data && data.status !== 'inactive') setActiveWorkflow(data); });
        }, 1500);
      }

    } catch (err) {
      setMessages((prev) => {
        return prev.map(m => m.id === jarvisMsgId ? { ...m, content: `Error communicating with server: ${err}`, isStreaming: false } : m);
      });
    } finally {
      setIsSending(false);
      setTimeout(() => {
        if (!isSpeakingRef.current) {
          if (sessionActiveRef.current) {
            setOrbState('listening');
            startSessionTimer();
          } else {
            setOrbState('idle');
          }
        }
      }, 50);
    }
  };

  // Workflow control actions
  const triggerWorkflowControl = (action: 'pause' | 'resume' | 'cancel' | 'approve') => {
    const currentWorkflow = activeWorkflowRef.current;
    if (!currentWorkflow) return;
    const objId = currentWorkflow.objective_id;

    fetch(`${BACKEND_URL}/api/autonomy/${action}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ objective_id: objId })
    })
      .then(() => {
        // Instant status refresh
        fetch(`${BACKEND_URL}/api/autonomy/status`)
          .then((res) => res.json())
          .then((data: WorkflowStatus) => {
            if (data && data.status !== 'inactive') setActiveWorkflow(data);
          });
      })
      .catch(() => {});
  };

  // Electron Bridge Events Listener
  useEffect(() => {
    if (!window.electronAPI) return;

    window.electronAPI.onVoiceToggle(() => {
      setVoiceActivationEnabled((prev) => !prev);
    });

    window.electronAPI.onApproveTask(() => {
      triggerWorkflowControl('approve');
    });

    window.electronAPI.onServerEvent((payload: any) => {
      if (payload && payload.event) {
        const timestamp = new Date().toLocaleTimeString();
        const eventName = payload.event;
        const detail = payload.data?.title || payload.data?.objective || payload.data?.error || '';
        setEventLogs((prev) => [`[${timestamp}] ${eventName}: ${detail}`, ...prev].slice(0, 30));
      }
    });
  }, []);

  // Preview file content in modal
  const openFilePreview = (filename: string, fileType: string) => {
    if (!activeWorkflow) return;
    const objId = activeWorkflow.objective_id;

    fetch(`${BACKEND_URL}/api/autonomy/artifact/content?objective_id=${objId}&filename=${filename}&file_type=${fileType}`)
      .then((res) => res.json())
      .then((data: { content: string }) => {
        if (data && data.content) {
          setPreviewFile({ name: filename, type: fileType, content: data.content });
        }
      })
      .catch(() => {});
  };

  if (window.location.search.includes('hud=true')) {
    return <HudView />;
  }

  return (
    <div className="app-container">
      {/* Sleek Header */}
      <header className="glass-panel header">
        <div className="logo-container">
          <Activity className="pulse-indicator cyan" />
          <h1 className="logo-text">Jarvis Core</h1>
        </div>
        <div className="header-status">
          <div className="status-item">
            <span className={`pulse-indicator ${apiConnected ? 'green' : 'red'}`} style={{ marginRight: '6px' }} />
            <span>{apiConnected ? 'API Connected (8765)' : 'Server Offline'}</span>
          </div>
          <div className="status-item">
            <span>Uptime: <strong style={{ color: 'var(--accent-cyan)' }}>Operational</strong></span>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center', marginLeft: '24px' }}>
          <button 
            onClick={() => setChatPanelCollapsed(!chatPanelCollapsed)} 
            className={`glass-button ${!chatPanelCollapsed ? 'active' : ''}`}
            style={{ fontSize: '11px', padding: '4px 10px', height: '28px' }}
          >
            {chatPanelCollapsed ? 'Show Chat' : 'Hide Chat'}
          </button>
        </div>
        {window.electronAPI && (
          <div className="window-controls">
            <button className="win-btn minimize" title="Minimize" onClick={() => window.electronAPI?.windowControl('minimize')} />
            <button className="win-btn close" title="Hide to Tray" onClick={() => window.electronAPI?.windowControl('close')} />
          </div>
        )}
      </header>

      {/* Main Split Panels */}
      <div className="main-content">
        {/* Left Control Panel / Status Panel */}
        <aside className="glass-panel sidebar">
          <div className="sidebar-section" style={{ borderBottom: '1px solid rgba(255,255,255,0.03)', paddingBottom: '16px' }}>
            <h2 className="sidebar-title">Active Objective</h2>
            {activeWorkflow ? (
              <div className="active-objective-card">
                {/* Title and ID */}
                <div className="objective-header">
                  <div className="objective-title">{activeWorkflow.objective}</div>
                  <div className="objective-id">ID: {activeWorkflow.objective_id}</div>
                </div>

                {/* Status Badge */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '4px' }}>
                  <span className={`pulse-indicator ${
                    activeWorkflow.status === 'running' ? 'cyan' : 
                    activeWorkflow.status === 'completed' ? 'green' : 'orange'
                  }`} />
                  <span className="status-text" style={{ 
                    color: activeWorkflow.status === 'running' ? 'var(--accent-cyan)' : 
                           activeWorkflow.status === 'completed' ? 'var(--accent-green)' : 'var(--accent-orange)'
                  }}>
                    {activeWorkflow.status}
                  </span>
                  {activeWorkflow.status === 'running' && (
                    <span className="spinner-mini" />
                  )}
                </div>

                {/* Progress Bar */}
                <div className="progress-section">
                  <div className="progress-labels">
                    <span>Progress</span>
                    <span>{activeWorkflow.completed_tasks}/{activeWorkflow.total_tasks} Tasks</span>
                  </div>
                  <div className="progress-track">
                    <div 
                      className="progress-fill"
                      style={{ width: `${activeWorkflow.progress * 100}%` }} 
                    />
                  </div>
                </div>

                {/* Real-time Sub-step / Active Task Card */}
                {activeWorkflow.status === 'running' && tasks.find(t => t.state === 'running' || t.state === 'awaiting_approval') && (() => {
                  const activeTask = tasks.find(t => t.state === 'running' || t.state === 'awaiting_approval')!;
                  const isAwaiting = activeTask.state === 'awaiting_approval';
                  return (
                    <div className={`active-task-card ${isAwaiting ? 'awaiting-approval' : ''}`} style={isAwaiting ? { borderLeftColor: 'var(--accent-orange)' } : {}}>
                      <div className="active-task-header">
                        <span className={`pulse-indicator ${isAwaiting ? 'orange' : 'cyan'}`} style={{ width: '8px', height: '8px', marginRight: '4px' }} />
                        <span>{isAwaiting ? 'Awaiting Permission' : 'Active Step'}: {activeTask.title}</span>
                      </div>
                      <div className="active-task-desc">{activeTask.description}</div>
                      {isAwaiting && (
                        <button 
                          onClick={() => triggerWorkflowControl('approve')} 
                          className="glass-button approve-button" 
                          style={{ marginTop: '10px', width: '100%', justifyContent: 'center' }}
                        >
                          <Check size={14} style={{ color: 'var(--accent-orange)' }} /> Approve Step
                        </button>
                      )}
                    </div>
                  );
                })()}

                {/* Objective completed success message */}
                {activeWorkflow.status === 'completed' && (
                  <div className="completed-success-banner" style={{
                    background: 'rgba(57, 255, 20, 0.08)',
                    border: '1px solid rgba(57, 255, 20, 0.2)',
                    borderRadius: '6px',
                    padding: '8px 12px',
                    marginTop: '12px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    color: 'var(--accent-green)',
                    fontSize: '12px'
                  }}>
                    <Check size={16} style={{ flexShrink: 0 }} />
                    <strong>Research & Deliverables Complete!</strong>
                  </div>
                )}

                {/* Latest Outputs / Deliverables Quick Access */}
                {artifacts.final_deliverables.length > 0 && (
                  <div className="quick-artifacts-section" style={{ marginTop: '12px' }}>
                    <div className="quick-artifacts-title">
                      {activeWorkflow.status === 'completed' ? 'Final Deliverables' : 'Latest Deliverables'}
                    </div>
                    <div className="quick-artifacts-list">
                      {(activeWorkflow.status === 'completed' ? artifacts.final_deliverables : artifacts.final_deliverables.slice(0, 3)).map((f) => (
                        <div key={f} className="quick-artifact-item" onClick={() => openFilePreview(f, 'final')}>
                          <FileText size={12} className="icon-cyan" />
                          <span className="truncate">{f}</span>
                        </div>
                      ))}
                    </div>
                    {window.electronAPI && activeWorkflow.status === 'completed' && (
                      <button 
                        onClick={() => {
                          const objId = activeWorkflow.objective_id;
                          const folderPath = `/home/pavan/jarvis/JarvisCore/workspace/${objId}/final_output`;
                          window.electronAPI?.openFolder(folderPath);
                        }}
                        className="glass-button"
                        style={{ marginTop: '10px', width: '100%', fontSize: '11px', justifyContent: 'center', height: '28px' }}
                      >
                        <Folder size={12} style={{ marginRight: '4px' }} /> Open Output Folder
                      </button>
                    )}
                  </div>
                )}

                {/* Autonomy Controls */}
                {activeWorkflow.objective_id !== 'deep_research' ? (
                  <div style={{ display: 'flex', gap: '8px', marginTop: '12px' }}>
                    {activeWorkflow.status === 'running' ? (
                      <button onClick={() => triggerWorkflowControl('pause')} className="glass-button" style={{ flex: 1 }}>
                        <Pause size={14} /> Pause
                      </button>
                    ) : (
                      <button 
                        onClick={() => triggerWorkflowControl('resume')} 
                        className="glass-button" 
                        style={{ flex: 1 }}
                        disabled={activeWorkflow.status === 'completed' || activeWorkflow.status === 'cancelled'}
                      >
                        <Play size={14} /> Resume
                      </button>
                    )}
                    <button 
                      onClick={() => triggerWorkflowControl('cancel')} 
                      className="glass-button" 
                      style={{ flex: 1, borderColor: 'rgba(255,0,85,0.2)' }}
                      disabled={activeWorkflow.status === 'completed' || activeWorkflow.status === 'cancelled'}
                    >
                      <Square size={14} style={{ color: 'var(--accent-red)' }} /> Cancel
                    </button>
                  </div>
                ) : (
                  <div className="chromium-active-badge">
                    <span className="pulse-indicator cyan" style={{ width: '8px', height: '8px', margin: '0' }} />
                    <span style={{ fontWeight: 500 }}>Chromium Active &mdash; Scraper Running</span>
                  </div>
                )}
              </div>
            ) : (
              <div className="no-objective-placeholder">
                No active execution workflow. Ask Jarvis to build deliverables or research to start one.
              </div>
            )}
          </div>

          {/* Workflow Tabs (Tasks vs Artifacts vs Security) */}
          <div className="sidebar-section" style={{ flex: 1 }}>
            <div style={{ display: 'flex', gap: '4px', marginBottom: '8px' }}>
              <button 
                onClick={() => setActiveTab('tasks')} 
                className={`glass-button ${activeTab === 'tasks' ? 'active' : ''}`}
                style={{ flex: 1, padding: '6px 2px', fontSize: '11px', justifyContent: 'center' }}
              >
                <Terminal size={12} style={{ marginRight: '2px' }} /> Task Graph
              </button>
              <button 
                onClick={() => setActiveTab('artifacts')} 
                className={`glass-button ${activeTab === 'artifacts' ? 'active' : ''}`}
                style={{ flex: 1, padding: '6px 2px', fontSize: '11px', justifyContent: 'center' }}
                disabled={!activeWorkflow}
              >
                <Folder size={12} style={{ marginRight: '2px' }} /> Deliverables
              </button>
              <button 
                onClick={() => setActiveTab('security')} 
                className={`glass-button ${activeTab === 'security' ? 'active' : ''}`}
                style={{ flex: 1, padding: '6px 2px', fontSize: '11px', justifyContent: 'center' }}
              >
                <Shield size={12} style={{ marginRight: '2px' }} /> Security
              </button>
            </div>

            {activeTab === 'tasks' ? (
              <div className="tasks-list">
                {tasks.length > 0 ? (
                  tasks.map((t) => (
                    <div key={t.id} className={`task-item ${t.state}`}>
                      <div className="task-header">
                        <span>{t.title}</span>
                        <span className={`task-status-badge badge-${t.state}`}>{t.state}</span>
                      </div>
                      <div className="task-desc">{t.description}</div>
                      {t.error_msg && (
                        <div style={{ color: 'var(--accent-red)', fontSize: '11px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                          <AlertTriangle size={10} /> {t.error_msg}
                        </div>
                      )}
                    </div>
                  ))
                ) : (
                  <div style={{ color: 'var(--text-muted)', fontSize: '13px', fontStyle: 'italic', padding: '10px 0' }}>
                    No tasks loaded.
                  </div>
                )}
              </div>
            ) : activeTab === 'artifacts' ? (
              <div className="tasks-list" style={{ gap: '10px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '12px', fontWeight: 600, color: 'var(--accent-cyan)' }}>
                  <span>Final Outputs</span>
                  {window.electronAPI && activeWorkflow && (
                    <span title="Reveal folder in explorer">
                      <Folder 
                        size={14} 
                        style={{ cursor: 'pointer', color: 'var(--accent-cyan)' }} 
                        onClick={(e) => {
                          e.stopPropagation();
                          const objId = activeWorkflow.objective_id;
                          const folderPath = `/home/pavan/jarvis/JarvisCore/workspace/${objId}/final_output`;
                          window.electronAPI?.openFolder(folderPath);
                        }}
                      />
                    </span>
                  )}
                </div>
                {artifacts.final_deliverables.map((f) => (
                  <div key={f} className="artifact-item" onClick={() => openFilePreview(f, 'final')}>
                    <FileText size={14} style={{ color: 'var(--accent-cyan)' }} />
                    <span style={{ fontWeight: 500 }}>{f}</span>
                  </div>
                ))}
                
                <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', marginTop: '8px' }}>Draft Artifacts</div>
                {artifacts.draft_artifacts.map((a) => (
                  <div key={a} className="artifact-item" onClick={() => openFilePreview(a, 'artifact')}>
                    <FileText size={14} />
                    <span>{a}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="security-panel-content" style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                {/* Diagnostics Shield Indicator */}
                <div className="security-status-card" style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '10px 12px',
                  borderRadius: '8px',
                  border: '1px solid rgba(255,255,255,0.04)',
                  background: 'rgba(255,255,255,0.01)'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Shield size={20} style={{ color: securityStatus?.status === 'ok' ? 'var(--accent-green)' : 'var(--accent-orange)' }} />
                    <div>
                      <div style={{ fontWeight: 600, fontSize: '13px' }}>Defensive Status</div>
                      <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                        {securityStatus?.status === 'ok' ? 'All local systems healthy' : 'Security Warning Active'}
                      </div>
                    </div>
                  </div>
                  <span className={`pulse-indicator ${securityStatus?.status === 'ok' ? 'green' : 'orange'}`} />
                </div>

                {/* Privacy Mode Selector */}
                <div>
                  <h3 style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '6px', letterSpacing: '1px' }}>Privacy Policy Mode</h3>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
                    {['normal', 'sensitive', 'offline', 'isolation'].map((m) => {
                      const active = (securityStatus?.privacy_mode || 'normal') === m;
                      return (
                        <button
                          key={m}
                          onClick={() => handleSetPrivacyMode(m)}
                          className={`glass-button ${active ? 'active' : ''}`}
                          style={{ padding: '6px 4px', fontSize: '11px', textTransform: 'capitalize', justifyContent: 'center' }}
                        >
                          {m === 'offline' && <WifiOff size={11} style={{ marginRight: '3px' }} />}
                          {m === 'normal' && <Globe size={11} style={{ marginRight: '3px' }} />}
                          {m}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Local Vault Panel */}
                <div style={{ borderTop: '1px solid rgba(255,255,255,0.03)', paddingTop: '10px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                    <h3 style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-muted)', letterSpacing: '1px' }}>Local Vault</h3>
                    <span style={{ fontSize: '10px', color: securityStatus?.vault?.locked ? 'var(--accent-orange)' : 'var(--accent-green)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '3px' }}>
                      {securityStatus?.vault?.locked ? <Lock size={10} /> : <Unlock size={10} />}
                      {securityStatus?.vault?.locked ? 'LOCKED' : 'UNLOCKED'}
                    </span>
                  </div>

                  {securityStatus?.vault?.locked ? (
                    <div style={{ display: 'flex', gap: '6px' }}>
                      <input
                        type="password"
                        placeholder="Vault password..."
                        value={vaultPassword}
                        onChange={(e) => setVaultPassword(e.target.value)}
                        className="chat-input"
                        style={{ padding: '6px 10px', fontSize: '12px', height: '30px' }}
                        onKeyDown={(e) => e.key === 'Enter' && handleUnlockVault()}
                      />
                      <button onClick={handleUnlockVault} className="glass-button" style={{ padding: '6px 10px', height: '30px', fontSize: '11px' }}>
                        Unlock
                      </button>
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      {/* Keys List */}
                      {securityStatus?.vault?.keys && securityStatus.vault.keys.length > 0 && (
                        <div style={{ maxHeight: '80px', overflowY: 'auto', border: '1px solid rgba(255,255,255,0.03)', borderRadius: '6px', padding: '6px', background: 'rgba(0,0,0,0.1)' }}>
                          <div style={{ fontSize: '10px', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '4px' }}>Secrets Stored:</div>
                          {securityStatus.vault.keys.map((k: string) => (
                            <div key={k} style={{ fontSize: '11px', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '4px', marginBottom: '2px' }}>
                              <Database size={10} /> {k}
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Set Secret Form */}
                      <div style={{ display: 'flex', gap: '4px' }}>
                         <input
                           type="text"
                           placeholder="Key..."
                           value={vaultNewKey}
                           onChange={(e) => setVaultNewKey(e.target.value)}
                           className="chat-input"
                           style={{ padding: '4px 6px', fontSize: '11px', height: '26px' }}
                         />
                         <input
                           type="password"
                           placeholder="Value..."
                           value={vaultNewValue}
                           onChange={(e) => setVaultNewValue(e.target.value)}
                           className="chat-input"
                           style={{ padding: '4px 6px', fontSize: '11px', height: '26px' }}
                         />
                         <button onClick={handleSetSecret} className="glass-button" style={{ padding: '4px 8px', height: '26px', fontSize: '11px' }}>
                           Save
                         </button>
                      </div>

                      <button onClick={handleLockVault} className="glass-button" style={{ width: '100%', padding: '6px', fontSize: '11px', justifyContent: 'center', borderColor: 'rgba(255,170,0,0.2)' }}>
                        <Lock size={12} style={{ marginRight: '4px' }} /> Lock Vault
                      </button>
                    </div>
                  )}
                </div>

                {/* Pending Gated Permissions */}
                {pendingPermissions.length > 0 && (
                  <div style={{ borderTop: '1px solid rgba(255,255,255,0.03)', paddingTop: '10px' }}>
                    <h3 style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', color: 'var(--accent-orange)', marginBottom: '6px', letterSpacing: '1px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <AlertTriangle size={12} /> Gated Approvals ({pendingPermissions.length})
                    </h3>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      {pendingPermissions.map((req) => (
                        <div key={req.id} style={{ padding: '8px', borderRadius: '6px', border: '1px solid rgba(255,170,0,0.2)', background: 'rgba(255,170,0,0.02)' }}>
                          <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-primary)' }}>{req.operation}</div>
                          <div style={{ fontSize: '10px', color: 'var(--text-secondary)', margin: '4px 0' }}>{req.details}</div>
                          <div style={{ display: 'flex', gap: '6px' }}>
                            <button onClick={() => handleResolvePermission(req.id, true)} className="glass-button" style={{ flex: 1, padding: '4px', fontSize: '10px', justifyContent: 'center', background: 'rgba(57,255,20,0.05)', borderColor: 'rgba(57,255,20,0.2)' }}>
                              Approve
                            </button>
                            <button onClick={() => handleResolvePermission(req.id, false)} className="glass-button" style={{ flex: 1, padding: '4px', fontSize: '10px', justifyContent: 'center', background: 'rgba(255,0,85,0.05)', borderColor: 'rgba(255,0,85,0.2)' }}>
                              Reject
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Audit Logs Stream */}
                <div style={{ borderTop: '1px solid rgba(255,255,255,0.03)', paddingTop: '10px' }}>
                  <h3 style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '6px', letterSpacing: '1px' }}>Local Security Logs</h3>
                  <div style={{
                    maxHeight: '120px',
                    overflowY: 'auto',
                    fontFamily: 'var(--font-mono)',
                    fontSize: '9px',
                    color: 'var(--text-secondary)',
                    background: 'rgba(0,0,0,0.2)',
                    padding: '6px',
                    borderRadius: '6px',
                    border: '1px solid rgba(255,255,255,0.02)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '4px'
                  }}>
                    {auditLogs.length > 0 ? (
                      auditLogs.map((log, idx) => (
                        <div key={idx} style={{
                          wordBreak: 'break-all',
                          borderBottom: '1px solid rgba(255,255,255,0.02)',
                          paddingBottom: '2px'
                        }}>
                          {log}
                        </div>
                      ))
                    ) : (
                      <div style={{ fontStyle: 'italic', color: 'var(--text-muted)' }}>No audit events logged.</div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* System Vitals & Event Stream Panel */}
          <div className="sidebar-section" style={{ borderTop: '1px solid rgba(255,255,255,0.03)', paddingTop: '16px', marginTop: '16px' }}>
            <h2 className="sidebar-title">System Diagnostics</h2>
            <div className="sidebar-vitals-grid">
              <div className="vital-widget">
                <span className="vital-widget-title">CPU Load</span>
                <span className="vital-widget-value">{cpuLoad}%</span>
              </div>
              <div className="vital-widget">
                <span className="vital-widget-title">CPU Temp</span>
                <span className="vital-widget-value">{cpuTemp}°C</span>
              </div>
              <div className="vital-widget">
                <span className="vital-widget-title">Memory</span>
                <span className="vital-widget-value">4.2 GB / 8.0 GB</span>
              </div>
              <div className="vital-widget">
                <span className="vital-widget-title">Ping</span>
                <span className="vital-widget-value">{pingMs}ms</span>
              </div>
            </div>
            
            {eventLogs.length > 0 && (
              <>
                <h2 className="sidebar-title" style={{ marginTop: '14px', marginBottom: '6px' }}>Event Stream</h2>
                <div className="event-logs-container">
                  {eventLogs.map((log, idx) => (
                    <div key={idx} className={`event-log-item ${log.includes('awaiting_approval') ? 'warning' : log.includes('completed') ? 'highlight' : ''}`}>
                      {log}
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        </aside>

        {/* Right Workspace Area containing Orb and Chat split */}
        <div className="workspace-area-split" style={{ gridTemplateColumns: chatPanelCollapsed ? '1fr' : '340px 1fr' }}>
          {/* JARVIS Glowing Orb Panel */}
          <div className="glass-panel orb-panel" style={chatPanelCollapsed ? { padding: '40px', justifyContent: 'center', height: '100%' } : {}}>
            <div className="orb-container" style={{ 
              width: chatPanelCollapsed ? '420px' : '260px', 
              height: chatPanelCollapsed ? '420px' : '280px', 
              marginBottom: '16px', 
              display: 'flex', 
              alignItems: 'center', 
              justifyContent: 'center' 
            }}>
              <CentralOrb state={orbState} size={chatPanelCollapsed ? 400 : 260} />
            </div>

            {/* Live Waveform Indicator (Simulated dynamic equalizer) */}
            <div className="simulated-equalizer" style={{ display: 'flex', gap: '4px', height: '24px', alignItems: 'flex-end', marginBottom: '24px' }}>
              {Array.from({ length: 15 }).map((_, i) => (
                <div 
                  key={i}
                  style={{
                    width: '4px',
                    backgroundColor: orbState === 'idle' ? 'var(--accent-cyan)' :
                                    orbState === 'listening' ? 'var(--accent-green)' :
                                    orbState === 'thinking' ? 'var(--accent-blue)' :
                                    'var(--accent-orange)',
                    borderRadius: '2px',
                    transition: 'all 0.15s ease',
                    height: `${eqHeights[i] || 4}px`,
                    opacity: 0.8
                  }}
                />
              ))}
            </div>

            {/* Diagnostics HUD Console */}
            <div className="diagnostics-console" style={chatPanelCollapsed ? { display: 'flex', flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'center', gap: '20px', width: '100%', maxWidth: '800px', padding: '10px' } : {}}>
              <div className="diagnostics-line">
                <span>INTERACTION MODE:</span>
                <span className="diagnostics-value" style={{ textTransform: 'uppercase', color: 'var(--accent-cyan)' }}>
                  {activeInteractionMode.replace('_', ' ')}
                </span>
              </div>
              <div className="diagnostics-line">
                <span>WAKE WORD WIDGET:</span>
                <span className="diagnostics-value" style={{ color: voiceActivationEnabled ? 'var(--accent-green)' : 'var(--text-muted)' }}>
                  {voiceActivationEnabled ? 'ON [JARVIS]' : 'OFF'}
                </span>
              </div>
              <div className="diagnostics-line">
                <span>SPEECH SYNTHESIS:</span>
                <span className="diagnostics-value" style={{ color: voiceResponseEnabled ? 'var(--accent-green)' : 'var(--text-muted)' }}>
                  {voiceResponseEnabled ? 'ACTIVE (GB)' : 'MUTED'}
                </span>
              </div>
              <div className="diagnostics-line">
                <span>COGNITIVE CORE:</span>
                <span className="diagnostics-value">OLLAMA + GEMINI</span>
              </div>
              <div className="diagnostics-line">
                <span>COGNITIVE LOAD:</span>
                <span className="diagnostics-value">{isSending ? 'PROCESSING' : 'STANDBY'}</span>
              </div>
              <div className="diagnostics-line">
                <span>CPU TEMP:</span>
                <span className="diagnostics-value">{cpuTemp}°C</span>
              </div>
              <div className="diagnostics-line">
                <span>NET PING:</span>
                <span className="diagnostics-value">{pingMs}ms</span>
              </div>
            </div>

            {/* Subtitle overlay for voice transcribing / speaking */}
            {chatPanelCollapsed && (messages.length > 0) && (
              <div 
                className="voice-subtitle-box" 
                style={{ 
                  marginTop: '24px', 
                  maxWidth: '700px', 
                  textAlign: 'center', 
                  fontSize: '16px', 
                  color: messages[messages.length - 1].role === 'user' ? 'var(--text-secondary)' : 'var(--accent-cyan)',
                  background: 'rgba(2, 8, 16, 0.75)',
                  padding: '10px 20px',
                  borderRadius: '8px',
                  border: '1px solid rgba(0, 240, 255, 0.15)',
                  backdropFilter: 'blur(8px)',
                  boxShadow: '0 4px 20px rgba(0, 240, 255, 0.05)',
                  lineHeight: '1.5',
                  wordBreak: 'break-word'
                }}
              >
                <strong style={{ textTransform: 'uppercase', fontSize: '11px', letterSpacing: '1px', display: 'block', marginBottom: '4px', color: 'var(--text-muted)' }}>
                  {messages[messages.length - 1].role === 'user' ? 'Vocal Input Detected' : 'J.A.R.V.I.S. Audio Response'}
                </strong>
                {messages[messages.length - 1].content}
              </div>
            )}

            {/* Voice & Chat Control Buttons */}
            <div style={{ display: 'flex', gap: '8px', width: chatPanelCollapsed ? '340px' : '100%', marginTop: '20px' }}>
              <button 
                onClick={() => setVoiceActivationEnabled(!voiceActivationEnabled)} 
                className={`glass-button ${voiceActivationEnabled ? 'active' : ''}`}
                style={{ flex: 1, fontSize: '11px', padding: '8px 4px', justifyContent: 'center' }}
                title={voiceActivationEnabled ? "Deactivate continuous microphone listening" : "Activate continuous wake-word listening"}
              >
                {voiceActivationEnabled ? <MicOff size={14} style={{ marginRight: '4px' }} /> : <Mic size={14} style={{ marginRight: '4px' }} />}
                {voiceActivationEnabled ? 'Mute Mic' : 'Listen Jarvis'}
              </button>
              <button 
                onClick={() => setVoiceResponseEnabled(!voiceResponseEnabled)} 
                className={`glass-button ${voiceResponseEnabled ? 'active' : ''}`}
                style={{ flex: 1, fontSize: '11px', padding: '8px 4px', justifyContent: 'center' }}
                title={voiceResponseEnabled ? "Deactivate speech feedback" : "Activate speech feedback"}
              >
                {voiceResponseEnabled ? <VolumeX size={14} style={{ marginRight: '4px' }} /> : <Volume2 size={14} style={{ marginRight: '4px' }} />}
                {voiceResponseEnabled ? 'Mute Speech' : 'Speak Responses'}
              </button>
              <button 
                onClick={() => setChatPanelCollapsed(!chatPanelCollapsed)} 
                className={`glass-button ${!chatPanelCollapsed ? 'active' : ''}`}
                style={{ flex: 1, fontSize: '11px', padding: '8px 4px', justifyContent: 'center' }}
                title={chatPanelCollapsed ? "Show text conversation console" : "Hide text conversation console"}
              >
                <Terminal size={14} style={{ marginRight: '4px' }} />
                {chatPanelCollapsed ? 'Show Chat' : 'Hide Chat'}
              </button>
            </div>
          </div>

          {/* Right Workspace Chat Panel */}
          {!chatPanelCollapsed && (
            <main className="workspace-area">
              <div className="glass-panel chat-panel">
                <div className="chat-messages">
                  {messages.map((m) => (
                    <div key={m.id} className={`message ${m.role}`}>
                      {m.role === 'jarvis' ? (
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                            <strong style={{ color: 'var(--accent-cyan)', fontSize: '12px' }}>
                              JARVIS
                            </strong>
                            {m.mode && (
                              <span className={`interaction-badge ${m.mode}`}>
                                {m.mode.replace('_', ' ').toUpperCase()}
                              </span>
                            )}
                            {speakingMessageId === m.id && (
                              <span className="speaking-indicator-tag">
                                🔊 SPEAKING
                              </span>
                            )}
                          </div>
                          <div style={{ fontSize: '13px', lineHeight: '1.5' }}>
                            <MarkdownRenderer content={m.content} />
                            {m.isStreaming && <span className="pulse-indicator cyan" style={{ marginLeft: '4px', width: '8px', height: '8px' }} />}
                          </div>
                        </div>
                      ) : (
                        <div style={{ fontSize: '13px' }}>{m.content}</div>
                      )}
                    </div>
                  ))}
                  <div ref={messagesEndRef} />
                </div>

                {/* Quick Reply Suggestion Chips */}
                {(() => {
                  const lastJarvisMsg = [...messages].reverse().find(msg => msg.role === 'jarvis');
                  const lastMode = lastJarvisMsg?.mode || 'conversational';
                  const suggestions = getSuggestionsForMode(lastMode);
                  if (suggestions.length === 0 || isSending) return null;
                  return (
                    <div className="suggestion-chips">
                      {suggestions.map((s, idx) => (
                        <button
                          key={idx}
                          className="suggestion-chip"
                          onClick={() => handleSendMessage(s)}
                        >
                          {s}
                        </button>
                      ))}
                    </div>
                  );
                })()}

                {/* Chat Input Bar */}
                <div className="input-bar" style={{ borderTop: '1px solid var(--border-glass)' }}>
                  <input
                    type="text"
                    className="chat-input"
                    placeholder="Instruct Jarvis..."
                    value={inputVal}
                    onChange={(e) => setInputVal(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
                    disabled={isSending || !apiConnected}
                  />
                  <button 
                    onClick={() => handleSendMessage()} 
                    className="glass-button active"
                    disabled={isSending || !apiConnected || !inputVal.trim()}
                  >
                    <Send size={16} />
                  </button>
                </div>
              </div>
            </main>
          )}
        </div>
      </div>

      {/* Code/File Preview Modal */}
      {previewFile && (
        <>
          <div className="overlay" onClick={() => setPreviewFile(null)} />
          <div className="glass-panel preview-modal">
            <div className="modal-header">
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <FileText size={18} style={{ color: 'var(--accent-cyan)' }} />
                <span style={{ fontWeight: 600, fontSize: '16px' }}>{previewFile.name}</span>
                <span style={{ fontSize: '11px', background: 'rgba(255,255,255,0.06)', padding: '2px 6px', borderRadius: '4px' }}>
                  {previewFile.type.toUpperCase()}
                </span>
              </div>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                {window.electronAPI && activeWorkflow && (
                  <button 
                    onClick={() => {
                      const objId = activeWorkflow.objective_id;
                      const subDir = previewFile.type === 'final' ? 'final_output' : 'artifacts';
                      const filePath = `/home/pavan/jarvis/JarvisCore/workspace/${objId}/${subDir}/${previewFile.name}`;
                      window.electronAPI?.openFile(filePath);
                    }} 
                    className="glass-button" 
                    style={{ fontSize: '11px', padding: '4px 10px', height: '30px' }}
                  >
                    Open in OS
                  </button>
                )}
                <button onClick={() => setPreviewFile(null)} className="glass-button" style={{ padding: '6px' }}>
                  <X size={16} />
                </button>
              </div>
            </div>
            <div className="modal-content">
              {previewFile.content}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
