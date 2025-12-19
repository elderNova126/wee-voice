import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import DashboardLayout from '../layouts/DashboardLayout';
import api from '../lib/api';
import { 
  ClipboardDocumentIcon, 
  CodeBracketIcon, 
  CheckCircleIcon, 
  GlobeAltIcon, 
  Cog6ToothIcon,
  ArrowLeftIcon,
  SparklesIcon,
  PaintBrushIcon,
  LanguageIcon,
  ChatBubbleLeftIcon,
  ShieldCheckIcon
} from '@heroicons/react/24/outline'
import { useTranslation } from '../lib/translations';
import toast from 'react-hot-toast';

interface EmbedConfig {
  embed_enabled: boolean;
  embed_widget_color: string;
  embed_position: string;
  embed_greeting_message: string;
  embed_language: string;
  allowed_domains: string[];
}

interface Agent {
  id: number;
  name: string;
  description: string;
  interaction_mode?: string;
}

export const AgentEmbedPage: React.FC = () => {
  const t = useTranslation();
  const { agentId } = useParams<{ agentId: string }>();
  const [agent, setAgent] = useState<Agent | null>(null);
  const [config, setConfig] = useState<EmbedConfig>({
    embed_enabled: false,
    embed_widget_color: '#4F46E5',
    embed_position: 'bottom-right',
    embed_greeting_message: '',
    embed_language: 'en',
    allowed_domains: []
  });
  const [embedCode, setEmbedCode] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);
  const [domainInput, setDomainInput] = useState('');

  useEffect(() => {
    loadAgent();
    loadEmbedConfig();
  }, [agentId]);

  const loadAgent = async () => {
    try {
      const response = await api.get(`/agents/${agentId}`);
      setAgent(response.data);
    } catch (error) {
      console.error('Error loading agent:', error);
    }
  };

  const loadEmbedConfig = async () => {
    try {
      const response = await api.get(`/embed/agents/${agentId}/embed-config`);
      setConfig(response.data);
      
      if (response.data.embed_enabled) {
        await loadEmbedCode();
      }
    } catch (error) {
      console.error('Error loading embed config:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadEmbedCode = async () => {
    try {
      const response = await api.get(`/embed/agents/${agentId}/embed-code`);
      setEmbedCode(response.data.embed_code);
    } catch (error) {
      console.error('Error loading embed code:', error);
    }
  };

  const handleSaveConfig = async () => {
    try {
      await api.put(`/embed/agents/${agentId}/embed-config`, config);
      
      if (config.embed_enabled) {
        await loadEmbedCode();
      }
      
      toast.success(t.agentEmbed.saveSuccess);
    } catch (error: any) {
      toast.error(t.agentEmbed.saveError + ': ' + (error.response?.data?.detail || error.message));
    }
  };

  const handleCopyCode = () => {
    navigator.clipboard.writeText(embedCode);
    setCopied(true);
    toast.success(t.agentEmbed.codeCopied);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleAddDomain = () => {
    if (domainInput && !config.allowed_domains.includes(domainInput)) {
      setConfig({
        ...config,
        allowed_domains: [...config.allowed_domains, domainInput]
      });
      setDomainInput('');
    }
  };

  const handleRemoveDomain = (domain: string) => {
    setConfig({
      ...config,
      allowed_domains: config.allowed_domains.filter(d => d !== domain)
    });
  };

  if (loading) {
    return (
      <DashboardLayout>
        <div className="space-y-6">
          <div className="h-9 w-64 bg-gray-200 dark:bg-gray-700 rounded animate-pulse mb-2"></div>
          <div className="h-96 bg-gray-200 dark:bg-gray-700 rounded-2xl animate-pulse"></div>
        </div>
      </DashboardLayout>
    );
  }

  const getModeText = () => {
    if (agent?.interaction_mode === 'text') return 'Text Chat';
    if (agent?.interaction_mode === 'both') return 'Voice & Text';
    return 'Voice';
  };

  return (
    <DashboardLayout>
      <div className="space-y-8">
        {/* Enhanced Header */}
        <div>
          <Link
            to="/dashboard/agents"
            className="inline-flex items-center text-sm font-medium text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-200 transition mb-4 group"
          >
            <ArrowLeftIcon className="mr-2 h-4 w-4 group-hover:-translate-x-1 transition-transform" />
            Back to Agents
          </Link>
          <div className="flex items-center gap-4">
            <div className="p-4 rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-500 shadow-lg">
              <CodeBracketIcon className="h-8 w-8 text-white" />
            </div>
            <div>
              <h1 className="text-4xl font-bold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">
                {t.agentEmbed.title} - {agent?.name || t.common.loading}
              </h1>
              <p className="mt-2 text-lg text-gray-600 dark:text-gray-400">
                {t.common.status === 'Statut' ? 'Configurez et intégrez votre agent dans votre site web' : 'Configure and integrate your agent into your website'}
              </p>
              {agent && (
                <div className="mt-2 inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-100 dark:bg-indigo-900 text-indigo-700 dark:text-indigo-300 text-sm font-medium">
                  <SparklesIcon className="h-4 w-4" />
                  {getModeText()} Mode
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Enhanced Configuration Section */}
        <Card className="border-2 border-gray-200 dark:border-gray-700 shadow-xl">
          <div className="relative">
            <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 rounded-t-xl"></div>
            <div className="p-6 lg:p-8">
              <div className="flex items-center gap-3 mb-8">
                <div className="p-3 rounded-xl bg-gradient-to-br from-indigo-100 to-purple-100 dark:from-indigo-900 dark:to-purple-900">
                  <Cog6ToothIcon className="text-indigo-600 dark:text-indigo-400 h-6 w-6" />
                </div>
                <div>
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
                    {t.agentEmbed.embedConfiguration}
                  </h2>
                  <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                    Customize how your agent appears on websites
                  </p>
                </div>
              </div>

              <div className="space-y-8">
                {/* Enable/Disable */}
                <div className="flex items-center justify-between p-6 bg-gradient-to-r from-gray-50 to-gray-100 dark:from-gray-800 dark:to-gray-900 rounded-2xl border border-gray-200 dark:border-gray-700">
                  <div className="flex-1">
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-1">
                      {t.agentEmbed.enableEmbed}
                    </h3>
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                      {t.common.status === 'Statut' ? 'Autoriser cet agent à être intégré sur les sites web' : 'Allow this agent to be embedded on websites'}
                    </p>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={config.embed_enabled}
                      onChange={(e) => setConfig({ ...config, embed_enabled: e.target.checked })}
                      className="sr-only peer"
                    />
                    <div className="w-14 h-7 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-indigo-300 dark:peer-focus:ring-indigo-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-6 after:w-6 after:transition-all dark:border-gray-600 peer-checked:bg-gradient-to-r peer-checked:from-indigo-600 peer-checked:to-purple-600"></div>
                  </label>
                </div>

                {/* Widget Color */}
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <PaintBrushIcon className="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
                    <label className="block text-sm font-semibold text-gray-900 dark:text-white">
                      {t.agentEmbed.widgetColor}
                    </label>
                  </div>
                  <div className="flex items-center gap-4">
                    <input
                      type="color"
                      value={config.embed_widget_color}
                      onChange={(e) => setConfig({ ...config, embed_widget_color: e.target.value })}
                      className="h-16 w-20 border-2 border-gray-300 dark:border-gray-600 rounded-xl cursor-pointer shadow-lg"
                    />
                    <input
                      type="text"
                      value={config.embed_widget_color}
                      onChange={(e) => setConfig({ ...config, embed_widget_color: e.target.value })}
                      className="flex-1 px-4 py-3 border-2 border-gray-300 dark:border-gray-600 rounded-xl dark:bg-gray-800 dark:border-gray-700 font-mono text-sm focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition"
                      placeholder="#4F46E5"
                    />
                  </div>
                </div>

                {/* Widget Position */}
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <GlobeAltIcon className="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
                    <label className="block text-sm font-semibold text-gray-900 dark:text-white">
                      {t.agentEmbed.widgetPosition}
                    </label>
                  </div>
                  <select
                    value={config.embed_position}
                    onChange={(e) => setConfig({ ...config, embed_position: e.target.value })}
                    className="w-full px-4 py-3 border-2 border-gray-300 dark:border-gray-600 rounded-xl dark:bg-gray-800 focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition font-medium"
                  >
                    <option value="bottom-right">{t.agentEmbed.bottomRight}</option>
                    <option value="bottom-left">{t.agentEmbed.bottomLeft}</option>
                    <option value="top-right">{t.agentEmbed.topRight}</option>
                    <option value="top-left">{t.agentEmbed.topLeft}</option>
                  </select>
                </div>

                {/* Widget Language */}
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <LanguageIcon className="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
                    <label className="block text-sm font-semibold text-gray-900 dark:text-white">
                      {t.common.status === 'Statut' ? 'Langue de l\'interface' : 'UI Language'}
                    </label>
                  </div>
                  <select
                    value={config.embed_language}
                    onChange={(e) => setConfig({ ...config, embed_language: e.target.value })}
                    className="w-full px-4 py-3 border-2 border-gray-300 dark:border-gray-600 rounded-xl dark:bg-gray-800 focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition font-medium"
                  >
                    <option value="en">🇬🇧 English</option>
                    <option value="fr">🇫🇷 Français</option>
                    <option value="es">🇪🇸 Español</option>
                    <option value="de">🇩🇪 Deutsch</option>
                    <option value="it">🇮🇹 Italiano</option>
                    <option value="pt">🇵🇹 Português</option>
                    <option value="zh">🇨🇳 中文</option>
                    <option value="ja">🇯🇵 日本語</option>
                    <option value="ko">🇰🇷 한국어</option>
                  </select>
                  <p className="text-xs text-gray-600 dark:text-gray-400">
                    {t.common.status === 'Statut' ? 'Sélectionnez la langue de l\'interface utilisateur du widget' : 'Select the language for the widget user interface'}
                  </p>
                </div>

                {/* Greeting Message */}
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <ChatBubbleLeftIcon className="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
                    <label className="block text-sm font-semibold text-gray-900 dark:text-white">
                      {t.agentEmbed.greetingMessage}
                    </label>
                  </div>
                  <textarea
                    value={config.embed_greeting_message}
                    onChange={(e) => setConfig({ ...config, embed_greeting_message: e.target.value })}
                    className="w-full px-4 py-3 border-2 border-gray-300 dark:border-gray-600 rounded-xl dark:bg-gray-800 focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition resize-none"
                    rows={3}
                    placeholder={`Hi! I'm ${agent?.name}. How can I help you?`}
                  />
                </div>

                {/* Allowed Domains */}
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <ShieldCheckIcon className="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
                    <label className="block text-sm font-semibold text-gray-900 dark:text-white">
                      {t.agentEmbed.allowedDomains} ({t.common.status === 'Statut' ? 'Optionnel' : 'Optional'})
                    </label>
                  </div>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    {t.common.status === 'Statut' ? 'Restreignez les sites web qui peuvent intégrer cet agent. Laissez vide pour autoriser tous les domaines.' : 'Restrict which websites can embed this agent. Leave empty to allow all domains.'}
                  </p>
                  
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={domainInput}
                      onChange={(e) => setDomainInput(e.target.value)}
                      onKeyPress={(e) => e.key === 'Enter' && handleAddDomain()}
                      className="flex-1 px-4 py-3 border-2 border-gray-300 dark:border-gray-600 rounded-xl dark:bg-gray-800 focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition"
                      placeholder={t.agentEmbed.domainPlaceholder}
                    />
                    <Button onClick={handleAddDomain} variant="outline" className="px-6 font-semibold">
                      Add
                    </Button>
                  </div>

                  {config.allowed_domains.length > 0 && (
                    <div className="flex flex-wrap gap-2 mt-3">
                      {config.allowed_domains.map((domain) => (
                        <div
                          key={domain}
                          className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-indigo-100 to-purple-100 dark:from-indigo-900 dark:to-purple-900 text-indigo-800 dark:text-indigo-200 rounded-xl border border-indigo-200 dark:border-indigo-800"
                        >
                          <GlobeAltIcon className="h-4 w-4" />
                          <span className="text-sm font-medium">{domain}</span>
                          <button
                            onClick={() => handleRemoveDomain(domain)}
                            className="text-indigo-600 dark:text-indigo-300 hover:text-indigo-800 dark:hover:text-indigo-100 font-bold ml-1"
                          >
                            ×
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Save Button */}
                <div className="pt-6 border-t-2 border-gray-200 dark:border-gray-700">
                  <Button 
                    onClick={handleSaveConfig} 
                    className="w-full py-4 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white font-bold text-lg shadow-xl hover:shadow-2xl transition-all transform hover:scale-105"
                  >
                    <CheckCircleIcon className="mr-2 h-5 w-5" />
                    {t.agentEmbed.saveConfig}
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </Card>

        {/* Enhanced Embed Code Section */}
        {config.embed_enabled && embedCode && (
          <Card className="border-2 border-gray-200 dark:border-gray-700 shadow-xl">
            <div className="relative">
              <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-green-500 via-emerald-500 to-teal-500 rounded-t-xl"></div>
              <div className="p-6 lg:p-8">
                <div className="flex items-center gap-3 mb-6">
                  <div className="p-3 rounded-xl bg-gradient-to-br from-green-100 to-emerald-100 dark:from-green-900 dark:to-emerald-900">
                    <CodeBracketIcon className="text-green-600 dark:text-green-400 h-6 w-6" />
                  </div>
                  <div>
                    <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
                      {t.agentEmbed.embedCode}
                    </h2>
                    <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                      Copy and paste this code into your website
                    </p>
                  </div>
                </div>

                <div className="space-y-6">
                  <div className="relative">
                    <pre className="bg-gray-900 text-gray-100 p-6 rounded-2xl overflow-x-auto text-sm font-mono border-2 border-gray-800">
                      <code>{embedCode}</code>
                    </pre>
                    <Button
                      onClick={handleCopyCode}
                      className="absolute top-4 right-4 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white font-semibold shadow-lg"
                      size="sm"
                    >
                      {copied ? (
                        <>
                          <CheckCircleIcon className="mr-2 h-4 w-4" />
                          {t.agentEmbed.codeCopied}
                        </>
                      ) : (
                        <>
                          <ClipboardDocumentIcon className="mr-2 h-4 w-4" />
                          {t.agentEmbed.copyCode}
                        </>
                      )}
                    </Button>
                  </div>

                  {/* Installation Instructions */}
                  <div className="bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20 p-6 rounded-2xl border-2 border-blue-200 dark:border-blue-800">
                    <h3 className="text-lg font-bold text-blue-900 dark:text-blue-200 mb-4 flex items-center gap-2">
                      <SparklesIcon className="h-5 w-5" />
                      {t.common.status === 'Statut' ? 'Instructions d\'installation' : 'Installation Instructions'}
                    </h3>
                    <ol className="list-decimal list-inside space-y-3 text-sm text-blue-800 dark:text-blue-300 font-medium">
                      <li>{t.common.status === 'Statut' ? 'Copiez le code d\'intégration ci-dessus' : 'Copy the embed code above'}</li>
                      <li>{t.common.status === 'Statut' ? 'Ouvrez le fichier HTML de votre site web' : 'Open your website\'s HTML file'}</li>
                      <li>{t.common.status === 'Statut' ? 'Collez le code juste avant la balise de fermeture' : 'Paste the code just before the closing'} &lt;/body&gt; {t.common.status === 'Statut' ? 'tag' : 'tag'}</li>
                      <li>{t.common.status === 'Statut' ? 'Enregistrez et déployez votre site web' : 'Save and deploy your website'}</li>
                      <li>{t.common.status === 'Statut' ? 'Le widget de l\'agent apparaîtra sur votre site web !' : 'The agent widget will appear on your website!'}</li>
                    </ol>
                  </div>

                  {/* Enhanced Preview */}
                  <div className="bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-800 dark:to-gray-900 p-6 rounded-2xl border-2 border-gray-200 dark:border-gray-700">
                    <h3 className="text-lg font-bold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                      <GlobeAltIcon className="h-5 w-5" />
                      {t.common.status === 'Statut' ? 'Aperçu' : 'Preview'}
                    </h3>
                    <div className="flex items-center gap-4 p-4 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
                      <div
                        className="w-20 h-20 rounded-full flex items-center justify-center shadow-xl"
                        style={{ backgroundColor: config.embed_widget_color }}
                      >
                        <CodeBracketIcon className="text-white h-10 w-10" />
                      </div>
                      <div className="flex-1">
                        <p className="text-lg font-bold text-gray-900 dark:text-white mb-1">
                          {t.common.status === 'Statut' ? 'Widget Agent' : 'Agent Widget'}
                        </p>
                        <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">
                          <span className="font-semibold">Position:</span> {config.embed_position === 'bottom-right' ? t.agentEmbed.bottomRight : config.embed_position === 'bottom-left' ? t.agentEmbed.bottomLeft : config.embed_position === 'top-right' ? t.agentEmbed.topRight : t.agentEmbed.topLeft}
                        </p>
                        <p className="text-sm text-gray-700 dark:text-gray-300 italic">
                          {config.embed_greeting_message || (t.common.status === 'Statut' ? `Bonjour ! Je suis ${agent?.name}. Comment puis-je vous aider ?` : `Hi! I'm ${agent?.name}. How can I help you?`)}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </Card>
        )}

        {!config.embed_enabled && (
          <Card className="border-2 border-dashed border-gray-300 dark:border-gray-700">
            <div className="text-center py-16">
              <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-gray-100 dark:bg-gray-800 mb-6">
                <CodeBracketIcon className="h-10 w-10 text-gray-400" />
              </div>
              <h3 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
                {t.common.status === 'Statut' ? 'Intégration non activée' : 'Embed Not Enabled'}
              </h3>
              <p className="text-gray-600 dark:text-gray-400 mb-6 max-w-md mx-auto">
                {t.common.status === 'Statut' ? 'Activez la fonctionnalité d\'intégration de site web ci-dessus pour générer votre code d\'intégration.' : 'Enable the website embed feature above to generate your embed code.'}
              </p>
              <Button
                onClick={() => setConfig({ ...config, embed_enabled: true })}
                className="bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white font-semibold"
              >
                Enable Embed
              </Button>
            </div>
          </Card>
        )}
      </div>
    </DashboardLayout>
  );
};
