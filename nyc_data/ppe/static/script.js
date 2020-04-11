function addUrlParameter(name, value) {
    var searchParams = new URLSearchParams(window.location.search);
    searchParams.set(name, value);
    window.location.search = searchParams.toString();
}

$(function(){

    // Rollup Toggle
    if($('#rollup-options.toggle').length > 0){
        $('#rollup-options.toggle a').click(function(e){
            e.preventDefault();
            // Get intended url parameter and set it on the current url
            // to prevent blowing away sort options
            var parms = $(this).attr('href').split('?')[1].split('=');
            addUrlParameter(parms[0], parms[1]);
        });

        $('#rollup-options.toggle li a').each(function(){
            var searchParams = new URLSearchParams(window.location.search);
            var parms = $(this).attr('href').split('?')[1].split('=');
            if(searchParams.has(parms[0])) {
                if(searchParams.get(parms[0]) == parms[1]){
                    $(this).parent().addClass('active');
                } else {
                    $(this).parent().removeClass('active');
                }
            }
        });
    }

});