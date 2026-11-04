// static/admin/js/product_order.js
django.jQuery(document).ready(function($) {
    var $form = $('#product_form');
    if (!$form.length) return;

    var $container = $form;

    // Бажаний порядок блоків зверху вниз за ключовими словами в їхніх заголовках (<h2>)
    var orderKeywords = [
        'ФОТО ТОВАРУ',
        'Основна інформація',
        'ЗАЛИШКИ',
        'ТОВАР КОМПЛЕКТУ',
        'ТАРА КОМПЛЕКТУ',
        'НАЛІПКА КОМПЛЕКТУ',
        'Тип та властивості',
        'Зовнішні посилання',
        'АНАЛОГИ'
    ];

    // Проходимо список у зворотному порядку і переносимо кожен блок наверх.
    // Завдяки цьому перший елемент у списку опиниться на самій верхівці сторінки.
    for (var i = orderKeywords.length - 1; i >= 0; i--) {
        var keyword = orderKeywords[i];
        
        $form.find('fieldset, .inline-group').each(function() {
            var $block = $(this);
            var headerText = $block.find('h2').text() || '';
            
            if (headerText.includes(keyword)) {
                $block.prependTo($container);
            }
        });
    }
});