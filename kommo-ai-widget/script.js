define(['jquery'], function ($) {
  return function CustomWidget() {
    var createStep = function (questions) {
      return {
        question: questions,
        require: []
      };
    };

    this.callbacks = {
      settings: function () {
        return true;
      },

      init: function () {
        return true;
      },

      bind_actions: function () {
        return true;
      },

      render: function () {
        return true;
      },

      destroy: function () {
        return true;
      },

      onSave: function () {
        return true;
      },

      onSalesbotDesignerSave: function (_handlerCode, params) {
        var hookUrl = params && params.url ? params.url : '';

        return JSON.stringify([
          createStep([
            {
              handler: 'widget_request',
              params: {
                url: hookUrl,
                data: {
                  from: 'ai_bridge',
                  message: '{{message_text}}',
                  lead_id: '{{lead.id}}',
                  contact_id: '{{contact.id}}'
                }
              }
            }
          ])
        ]);
      }
    };

    return this;
  };
});
