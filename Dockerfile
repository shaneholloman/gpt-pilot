# Use Ubuntu 22.04 as the base image with multi-arch support
FROM ubuntu:22.04

# Use buildx args for multi-arch support
ARG TARGETPLATFORM
ARG BUILDPLATFORM

# Set defaults for TARGETPLATFORM to ensure it's available in scripts
ENV TARGETPLATFORM=${TARGETPLATFORM:-linux/amd64}

# Copy VSIX file first
COPY pythagora-vs-code.vsix /var/init_data/pythagora-vs-code.vsix

# Install all dependencies
COPY cloud/setup-dependencies.sh /tmp/setup-dependencies.sh
RUN chmod +x /tmp/setup-dependencies.sh && \
    /tmp/setup-dependencies.sh && \
    rm /tmp/setup-dependencies.sh

ENV PYTH_INSTALL_DIR=/pythagora

# Set up work directory
WORKDIR ${PYTH_INSTALL_DIR}/pythagora-core

# Add Python requirements
ADD requirements.txt .

# Create and activate a virtual environment, then install dependencies
RUN python3 -m venv venv && \
    . venv/bin/activate && \
    pip install -r requirements.txt

# Copy application files
ADD main.py .
ADD core core
ADD pyproject.toml .
ADD cloud/config-docker.json config.json

# Set the virtual environment to be automatically activated
ENV VIRTUAL_ENV=${PYTH_INSTALL_DIR}/pythagora-core/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

ENV PYTHAGORA_DATA_DIR=${PYTH_INSTALL_DIR}/pythagora-core/data/
RUN mkdir -p data

# Expose MongoDB and application ports
EXPOSE 27017 8000 8080 5173 3000

# Create a group and user
RUN groupadd -g 1000 devusergroup && \
    useradd -m -u 1000 -g devusergroup -s /bin/bash devuser && \
    echo "devuser:devuser" | chpasswd && \
    adduser devuser sudo && \
    echo "devuser ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# Set up entrypoint and VS Code extension
ADD cloud/entrypoint.sh /entrypoint.sh
ADD cloud/on-event-extension-install.sh /var/init_data/on-event-extension-install.sh
ADD cloud/favicon.svg /favicon.svg
ADD cloud/favicon.ico /favicon.ico

# Create necessary directories with proper permissions for code-server
RUN mkdir -p /usr/local/share/code-server/data/User/globalStorage && \
    mkdir -p /usr/local/share/code-server/data/User/History && \
    mkdir -p /usr/local/share/code-server/data/Machine && \
    mkdir -p /usr/local/share/code-server/data/logs

# Add code server settings.json
ADD cloud/settings.json /usr/local/share/code-server/data/Machine/settings.json

RUN chown -R devuser:devusergroup /usr/local/share/code-server && \
    chmod -R 755 /usr/local/share/code-server && \
    # Copy icons
    cp -f /favicon.ico /usr/local/lib/code-server/src/browser/media/favicon.ico && \
    cp -f /favicon.svg /usr/local/lib/code-server/src/browser/media/favicon-dark-support.svg && \
    cp -f /favicon.svg /usr/local/lib/code-server/src/browser/media/favicon.svg

# Configure PostHog analytics integration
RUN sed -i "s|'sha256-/r7rqQ+yrxt57sxLuQ6AMYcy/lUpvAIzHjIJt/OeLWU=' ;|'sha256-/r7rqQ+yrxt57sxLuQ6AMYcy/lUpvAIzHjIJt/OeLWU=' https://us-assets.i.posthog.com ;|g" /usr/local/lib/code-server/lib/vscode/out/server-main.js && \
    sed -i '/<head>/r /dev/stdin' /usr/local/lib/code-server/lib/vscode/out/vs/code/browser/workbench/workbench.html << 'EOF'
<script>
    !function(t,e){var o,n,p,r;e.__SV||(window.posthog=e,e._i=[],e.init=function(i,s,a){function g(t,e){var o=e.split(".");2==o.length&&(t=t[o[0]],e=o[1]),t[e]=function(){t.push([e].concat(Array.prototype.slice.call(arguments,0)))}}(p=t.createElement("script")).type="text/javascript",p.crossOrigin="anonymous",p.async=!0,p.src=s.api_host.replace(".i.posthog.com","-assets.i.posthog.com")+"/static/array.js",(r=t.getElementsByTagName("script")[0]).parentNode.insertBefore(p,r);var u=e;for(void 0!==a?u=e[a]=[]:a="posthog",u.people=u.people||[],u.toString=function(t){var e="posthog";return"posthog"!==a&&(e+="."+a),t||(e+=" (stub)"),e},u.people.toString=function(){return u.toString(1)+".people (stub)"},o="init Ie Ts Ms Ee Es Rs capture Ge calculateEventProperties Os register register_once register_for_session unregister unregister_for_session js getFeatureFlag getFeatureFlagPayload isFeatureEnabled reloadFeatureFlags updateEarlyAccessFeatureEnrollment getEarlyAccessFeatures on onFeatureFlags onSurveysLoaded onSessionId getSurveys getActiveMatchingSurveys renderSurvey canRenderSurvey canRenderSurveyAsync identify setPersonProperties group resetGroups setPersonPropertiesForFlags resetPersonPropertiesForFlags setGroupPropertiesForFlags resetGroupPropertiesForFlags reset get_distinct_id getGroups get_session_id get_session_replay_url alias set_config startSessionRecording stopSessionRecording sessionRecordingStarted captureException loadToolbar get_property getSessionProperty Ds Fs createPersonProfile Ls Ps opt_in_capturing opt_out_capturing has_opted_in_capturing has_opted_out_capturing clear_opt_in_out_capturing Cs debug I As getPageViewId captureTraceFeedback captureTraceMetric".split(" "),n=0;n<o.length;n++)g(u,o[n]);e._i.push([i,s,a])},e.__SV=1)}(document,window.posthog||[]);
    posthog.init('phc_OhmNscA1dbQ0icZy4KZ2nmqUoxYGOwVsjO7VnwfMR7Q', {
        api_host: 'https://us.i.posthog.com',
        defaults: '2025-05-24',
        person_profiles: 'always',
    })

    const userEmail = "test@gmail.com";
    window.posthog.identify(userEmail, {
                email: userEmail
    });
</script>
EOF

RUN chmod +x /entrypoint.sh && \
    chmod +x /var/init_data/on-event-extension-install.sh && \
    chown -R devuser:devusergroup /pythagora && \
    chown -R devuser: /var/init_data/

# Create workspace directory
RUN mkdir -p ${PYTH_INSTALL_DIR}/pythagora-core/workspace && \
    chown -R devuser:devusergroup ${PYTH_INSTALL_DIR}/pythagora-core/workspace

# Set up git config
RUN su -c "git config --global user.email 'devuser@pythagora.ai'" devuser && \
    su -c "git config --global user.name 'pythagora'" devuser

# Remove the USER directive to keep root as the running user
ENTRYPOINT ["/entrypoint.sh"]